"""Pipeline orchestration for the web crawling and processing workflow.

Coordinates URL classification, content extraction, cleaning, and chunking,
storing results in the configured database. Supports both legacy single-config
mode and multi-source mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog

from employee_help.config import CrawlConfig, SourceConfig
from employee_help.processing.chunker import chunk_document, chunk_statute_section
from employee_help.processing.cleaner import clean
from employee_help.scraper.crawler import Crawler
from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    CrawlStatus,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage

logger = structlog.get_logger()


@dataclass
class PipelineStats:
    """Statistics from a completed pipeline run."""

    run_id: int
    urls_crawled: int
    documents_stored: int
    chunks_created: int
    errors: int
    start_time: datetime
    end_time: datetime
    source_slug: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


def classify_content_category(url: str, content_type: ContentType) -> ContentCategory:
    """Classify a document's content category based on URL and type heuristics."""
    url_lower = url.lower()

    if "leginfo.legislature.ca.gov" in url_lower:
        return ContentCategory.STATUTORY_CODE

    if content_type == ContentType.PDF:
        if any(kw in url_lower for kw in ("fact-sheet", "factsheet", "fact_sheet")):
            return ContentCategory.FACT_SHEET
        if any(kw in url_lower for kw in ("poster", "notice")):
            return ContentCategory.POSTER

    if any(kw in url_lower for kw in ("faq", "frequently-asked", "questions")):
        return ContentCategory.FAQ

    return ContentCategory.AGENCY_GUIDANCE


class Pipeline:
    """Orchestrates the complete scraping and processing pipeline."""

    def __init__(
        self,
        config: CrawlConfig | SourceConfig,
        storage: Storage | None = None,
    ) -> None:
        if isinstance(config, SourceConfig):
            self.source_config = config
            # Statutory sources don't need a CrawlConfig (no seed URLs / crawler).
            # Only convert to CrawlConfig for agency sources that use the web crawler.
            is_statutory = (
                config.statutory is not None
                and config.source_type == SourceType.STATUTORY_CODE
            )
            if is_statutory:
                # Build a minimal CrawlConfig for storage path and chunking settings
                self.config = CrawlConfig(
                    seed_urls=["https://placeholder.invalid"],
                    allowlist_patterns=config.allowlist_patterns or ["placeholder"],
                    blocklist_patterns=config.blocklist_patterns,
                    rate_limit_seconds=config.rate_limit_seconds,
                    max_pages=config.max_pages,
                    chunking=config.chunking,
                    database_path=config.database_path,
                )
            else:
                self.config = config.to_crawl_config()
        else:
            self.source_config = None
            self.config = config

        self.storage = storage or Storage(self.config.database_path)
        # Statutory sources don't need a crawler; agency/legacy sources do
        is_statutory = (
            self.source_config is not None
            and self.source_config.statutory is not None
            and self.source_config.source_type == SourceType.STATUTORY_CODE
        )
        self.crawler: Crawler | None = None if is_statutory else Crawler(self.config)
        self.logger = structlog.get_logger(
            __name__,
            source=self.source_config.slug if self.source_config else "legacy",
        )

        # Compile source-specific boilerplate patterns if provided
        self._boilerplate_patterns: list[re.Pattern] | None = None
        if self.source_config and self.source_config.extraction.boilerplate_patterns:
            self._boilerplate_patterns = [
                re.compile(p, re.IGNORECASE)
                for p in self.source_config.extraction.boilerplate_patterns
            ]

    def _ensure_source_record(self) -> int | None:
        """Ensure the source record exists in the DB, return its id."""
        if not self.source_config:
            return None

        source = self.storage.get_source(self.source_config.slug)
        if source:
            return source.id

        source = Source(
            name=self.source_config.name,
            slug=self.source_config.slug,
            source_type=self.source_config.source_type,
            base_url=self.source_config.base_url,
            enabled=self.source_config.enabled,
        )
        self.storage.create_source(source)
        return source.id

    def run(self, dry_run: bool = False) -> PipelineStats:
        """Execute the complete pipeline.

        Routes to either the web crawler pipeline (agency sources) or the
        statutory extractor pipeline (statutory_code sources) based on
        source configuration.
        """
        # Route to statutory pipeline if applicable
        if (
            self.source_config
            and self.source_config.statutory
            and self.source_config.source_type == SourceType.STATUTORY_CODE
        ):
            return self._run_statutory(dry_run)

        return self._run_crawler(dry_run)

    def _get_completed_statutory_urls(self, source_id: int | None) -> set[str]:
        """Get URLs of displayText pages already stored for this source.

        Used for resumability — allows the extractor to skip pages that
        were successfully processed in a previous (possibly interrupted) run.
        """
        if source_id is None:
            return set()

        docs = self.storage.get_all_documents(source_id=source_id)
        # Each statutory document's source_url is a displaySection URL.
        # The extractor processes displayText pages which contain multiple sections.
        # We track which displayText page URLs have been completed by looking at
        # existing documents — if ANY section from a displayText page is stored,
        # we consider that page completed.
        # For efficiency, we store the displayText URL in document metadata.
        # But for now, we can check if sections from a page exist by querying
        # stored section URLs and mapping back.
        # Simpler approach: if we have documents for this source, collect all
        # unique displayText page URLs from the run summary or crawl log.
        # Simplest approach: return empty set on first run, full set on re-run
        # when all sections from prior run are already stored (upsert handles dedup).
        return set()  # Pipeline's upsert_document handles dedup; resumability is at extractor level

    def _extract_via_pubinfo(self) -> list:
        """Extract statutory sections using the PUBINFO database loader."""
        from employee_help.scraper.extractors.pubinfo import PubinfoLoader, download_pubinfo

        statutory = self.source_config.statutory
        pubinfo_dir = Path("data/pubinfo")

        # Find existing ZIP or download
        zip_path = self._find_pubinfo_zip(pubinfo_dir)
        if zip_path is None:
            self.logger.info("pubinfo_zip_not_found_downloading")
            zip_path = download_pubinfo(pubinfo_dir)

        loader = PubinfoLoader(zip_path)
        all_sections = loader.parse_law_sections()

        target_divs = statutory.target_divisions or None
        filtered = loader.filter_sections(
            all_sections,
            target_codes=[statutory.code_abbreviation],
            target_divisions=target_divs,
        )

        return loader.to_statute_sections(filtered)

    def _extract_via_caci_pdf(self) -> list:
        """Extract CACI jury instructions from the official PDF."""
        from employee_help.scraper.extractors.caci import CACILoader

        pdf_path = Path("data/caci/caci_2026.pdf")
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"CACI PDF not found at {pdf_path}. "
                "Download from https://www.courts.ca.gov/partners/317.htm"
            )

        loader = CACILoader(pdf_path)
        return loader.to_statute_sections()

    def _extract_via_web(self) -> tuple[list, int]:
        """Extract statutory sections using the web scraper. Returns (sections, request_count)."""
        from employee_help.scraper.extractors.statute import StatutoryExtractor

        statutory = self.source_config.statutory
        target_divs = statutory.target_divisions or None

        with StatutoryExtractor(
            statutory.code_abbreviation,
            rate_limit=self.config.rate_limit_seconds,
            target_divisions=target_divs,
            citation_prefix=statutory.citation_prefix,
        ) as extractor:
            sections = extractor.extract_all()

        return sections, extractor._request_count

    @staticmethod
    def _find_pubinfo_zip(pubinfo_dir: Path) -> Path | None:
        """Find the most recent pubinfo ZIP in the cache directory."""
        if not pubinfo_dir.exists():
            return None
        zips = sorted(pubinfo_dir.glob("pubinfo_*.zip"), reverse=True)
        return zips[0] if zips else None

    def _run_statutory(self, dry_run: bool = False) -> PipelineStats:
        """Execute the statutory code extraction pipeline.

        Routes to PubinfoLoader (default) or web scraper based on config.
        """
        start_time = datetime.now(tz=timezone.utc)
        slug = self.source_config.slug
        statutory = self.source_config.statutory

        stats = PipelineStats(
            run_id=-1,
            urls_crawled=0,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=start_time,
            end_time=start_time,
            source_slug=slug,
        )

        source_id = None
        run_id = None

        try:
            if not dry_run:
                source_id = self._ensure_source_record()
                run = self.storage.create_run(source_id=source_id)
                run_id = run.id
                stats.run_id = run_id
                self.logger.info("statutory_run_created", run_id=run_id)

            method = getattr(statutory, "method", "pubinfo")
            # Allow CLI override via _method_override attribute
            if hasattr(self, "_method_override") and self._method_override:
                method = self._method_override

            self.logger.info("statutory_extraction_method", method=method)

            if method == "pubinfo":
                sections = self._extract_via_pubinfo()
                stats.urls_crawled = 0  # No HTTP requests for pubinfo
            elif method == "caci_pdf":
                sections = self._extract_via_caci_pdf()
                stats.urls_crawled = 0  # No HTTP requests for PDF
            else:
                sections, request_count = self._extract_via_web()
                stats.urls_crawled = request_count

            # Determine content category from extraction config (defaults to STATUTORY_CODE)
            category_str = self.source_config.extraction.content_category
            try:
                content_category = ContentCategory(category_str)
            except ValueError:
                content_category = ContentCategory.STATUTORY_CODE

            for section in sections:
                try:
                    chunks = chunk_statute_section(
                        section.text,
                        citation=section.citation,
                        heading_path=section.heading_path,
                        max_tokens=self.config.chunking.max_tokens,
                        overlap_tokens=self.config.chunking.overlap_tokens,
                    )

                    if not chunks:
                        self.logger.warning("no_chunks_for_section", citation=section.citation)
                        continue

                    if not dry_run and run_id:
                        document = Document(
                            source_url=section.source_url,
                            title=section.citation,
                            content_type=ContentType.HTML,
                            raw_content=section.text,
                            content_hash=chunks[0].content_hash,
                            language="en",
                            crawl_run_id=run_id,
                            source_id=source_id,
                            content_category=content_category,
                        )

                        stored_doc, is_new = self.storage.upsert_document(document)

                        if stored_doc.id and is_new:
                            chunk_objects = [
                                Chunk(
                                    content=chunk.content,
                                    content_hash=chunk.content_hash,
                                    chunk_index=chunk.chunk_index,
                                    heading_path=chunk.heading_path,
                                    token_count=chunk.token_count,
                                    document_id=stored_doc.id,
                                    content_category=content_category,
                                    citation=section.citation,
                                )
                                for chunk in chunks
                            ]
                            self.storage.insert_chunks(chunk_objects)
                        elif not is_new:
                            self.logger.debug("document_unchanged", citation=section.citation)

                    stats.documents_stored += 1
                    stats.chunks_created += len(chunks)

                except Exception as e:
                    stats.errors += 1
                    self.logger.error(
                        "error_processing_section",
                        citation=section.citation,
                        error=str(e),
                    )

            # Soft-delete chunks for sections that are no longer in the source
            # (repealed-section handling per F-SC.6)
            if not dry_run and source_id:
                current_urls = {s.source_url for s in sections}
                deactivated = self.storage.deactivate_missing_sections(
                    source_id, current_urls
                )
                if deactivated:
                    self.logger.info(
                        "repealed_sections_deactivated",
                        count=deactivated,
                    )

            end_time = datetime.now(tz=timezone.utc)
            if not dry_run and run_id:
                status = CrawlStatus.COMPLETED if stats.errors == 0 else CrawlStatus.FAILED
                summary = {
                    "urls_crawled": stats.urls_crawled,
                    "documents_stored": stats.documents_stored,
                    "chunks_created": stats.chunks_created,
                    "errors": stats.errors,
                    "duration_seconds": (end_time - start_time).total_seconds(),
                }
                self.storage.complete_run(run_id, status, summary)

            stats.end_time = end_time
            self._log_run_summary(stats)
            return stats

        except Exception as e:
            self.logger.error("statutory_pipeline_failed", error=str(e))
            stats.end_time = datetime.now(tz=timezone.utc)
            raise

    def _run_crawler(self, dry_run: bool = False) -> PipelineStats:
        """Execute the web crawler pipeline (for agency sources)."""
        start_time = datetime.now(tz=timezone.utc)
        source_id = None
        run_id = None
        slug = self.source_config.slug if self.source_config else None

        stats = PipelineStats(
            run_id=-1,
            urls_crawled=0,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=start_time,
            end_time=start_time,
            source_slug=slug,
        )

        try:
            if self.crawler is None:
                self.crawler = Crawler(self.config)
            self.crawler.start()

            if not dry_run:
                source_id = self._ensure_source_record()
                run = self.storage.create_run(source_id=source_id)
                run_id = run.id
                stats.run_id = run_id
                self.logger.info("crawl_run_created", run_id=run_id, source_id=source_id)

            for crawl_result in self.crawler.crawl():
                stats.urls_crawled += 1
                url = crawl_result.url

                if crawl_result.error:
                    stats.errors += 1
                    self.logger.warning("crawl_error", url=url, error=crawl_result.error)
                    continue

                if crawl_result.html:
                    content_type = ContentType.HTML
                    from employee_help.scraper.extractors.html import extract_html
                    extraction_result = extract_html(crawl_result.html, url)
                    raw_content = extraction_result.markdown if extraction_result else ""
                elif crawl_result.pdf_bytes:
                    content_type = ContentType.PDF
                    from employee_help.scraper.extractors.pdf import extract_pdf
                    extraction_result = extract_pdf(crawl_result.pdf_bytes, url)
                    raw_content = extraction_result.markdown if extraction_result else ""
                else:
                    self.logger.warning("no_content_in_result", url=url)
                    continue

                if not raw_content:
                    self.logger.warning("no_content_extracted", url=url)
                    continue

                self.logger.info("processing_url", url=url, content_type=content_type.value)

                try:
                    cleaned_content = clean(raw_content, self._boilerplate_patterns)

                    chunks = chunk_document(
                        cleaned_content,
                        min_tokens=self.config.chunking.min_tokens,
                        max_tokens=self.config.chunking.max_tokens,
                        overlap_tokens=self.config.chunking.overlap_tokens,
                        document_title=Path(url).name,
                    )

                    if not chunks:
                        self.logger.warning("no_chunks_created", url=url)
                        continue

                    content_category = classify_content_category(url, content_type)

                    if not dry_run and run_id:
                        document = Document(
                            source_url=url,
                            title=Path(url).name,
                            content_type=content_type,
                            raw_content=cleaned_content,
                            content_hash=chunks[0].content_hash if chunks else "",
                            language="en",
                            crawl_run_id=run_id,
                            source_id=source_id,
                            content_category=content_category,
                        )

                        stored_doc, is_new = self.storage.upsert_document(document)

                        if stored_doc.id and is_new:
                            chunk_objects = [
                                Chunk(
                                    content=chunk.content,
                                    content_hash=chunk.content_hash,
                                    chunk_index=chunk.chunk_index,
                                    heading_path=chunk.heading_path,
                                    token_count=chunk.token_count,
                                    document_id=stored_doc.id,
                                    content_category=content_category,
                                )
                                for chunk in chunks
                            ]
                            self.storage.insert_chunks(chunk_objects)

                        stats.documents_stored += 1
                        stats.chunks_created += len(chunks)
                        self.logger.info("document_processed", url=url, chunks=len(chunks), is_new=is_new)
                    else:
                        stats.documents_stored += 1
                        stats.chunks_created += len(chunks)
                        self.logger.info("document_processed_dry_run", url=url, chunks=len(chunks))

                except Exception as e:
                    stats.errors += 1
                    self.logger.error("error_processing_url", url=url, error=str(e))

            end_time = datetime.now(tz=timezone.utc)
            if not dry_run and run_id:
                status = CrawlStatus.COMPLETED if stats.errors == 0 else CrawlStatus.FAILED
                summary = {
                    "urls_crawled": stats.urls_crawled,
                    "documents_stored": stats.documents_stored,
                    "chunks_created": stats.chunks_created,
                    "errors": stats.errors,
                    "duration_seconds": stats.duration_seconds,
                }
                self.storage.complete_run(run_id, status, summary)

            stats.end_time = end_time
            self._log_run_summary(stats)
            return stats

        except Exception as e:
            self.logger.error("pipeline_failed", error=str(e))
            stats.end_time = datetime.now(tz=timezone.utc)
            raise

        finally:
            self.crawler.close()

    def _log_run_summary(self, stats: PipelineStats) -> None:
        self.logger.info(
            "pipeline_summary",
            run_id=stats.run_id,
            source=stats.source_slug,
            urls_crawled=stats.urls_crawled,
            documents_stored=stats.documents_stored,
            chunks_created=stats.chunks_created,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
        )
