"""Pipeline orchestration for the web crawling and processing workflow.

Coordinates URL classification, content extraction, cleaning, and chunking,
storing results in the configured database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog

from employee_help.config import CrawlConfig
from employee_help.processing.chunker import chunk_document
from employee_help.processing.cleaner import clean
from employee_help.scraper.crawler import Crawler, UrlClassification
from employee_help.scraper.extractors.html import extract_html
from employee_help.scraper.extractors.pdf import extract_pdf
from employee_help.storage.models import Chunk, ContentType, CrawlStatus, Document
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

    @property
    def duration_seconds(self) -> float:
        """Total duration of the run in seconds."""
        return (self.end_time - self.start_time).total_seconds()


class Pipeline:
    """Orchestrates the complete scraping and processing pipeline."""

    def __init__(self, config: CrawlConfig) -> None:
        """Initialize the pipeline with configuration.

        Args:
            config: CrawlConfig instance with crawling and processing parameters.
        """
        self.config = config
        self.storage = Storage(config.database_path)
        self.crawler = Crawler(config)
        self.logger = structlog.get_logger(__name__)

    def run(self, dry_run: bool = False) -> PipelineStats:
        """Execute the complete pipeline.

        Args:
            dry_run: If True, perform crawling but skip storage operations.
                Useful for validation and testing.

        Returns:
            PipelineStats with summary information about the run.
        """
        start_time = datetime.now(tz=timezone.utc)
        run_id = None
        stats = PipelineStats(
            run_id=-1,
            urls_crawled=0,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=start_time,
            end_time=start_time,
        )

        try:
            # Start the browser
            self.crawler.start()

            # Create crawl run record
            if not dry_run:
                run = self.storage.create_run()
                run_id = run.id
                stats.run_id = run_id
                self.logger.info("crawl_run_created", run_id=run_id)

            # Execute crawl and process each page
            for crawl_result in self.crawler.crawl():
                stats.urls_crawled += 1
                url = crawl_result.url

                # Skip errors
                if crawl_result.error:
                    stats.errors += 1
                    self.logger.warning(
                        "crawl_error",
                        url=url,
                        error=crawl_result.error,
                        run_id=run_id,
                    )
                    continue

                # Determine content type and extract
                if crawl_result.html:
                    content_type = ContentType.HTML
                    extraction_result = extract_html(crawl_result.html, url)
                    raw_content = extraction_result.markdown if extraction_result else ""
                elif crawl_result.pdf_bytes:
                    content_type = ContentType.PDF
                    extraction_result = extract_pdf(crawl_result.pdf_bytes, url)
                    raw_content = extraction_result.markdown if extraction_result else ""
                else:
                    self.logger.warning(
                        "no_content_in_result",
                        url=url,
                        run_id=run_id,
                    )
                    continue

                if not raw_content:
                    self.logger.warning("no_content_extracted", url=url, run_id=run_id)
                    continue

                self.logger.info(
                    "processing_url",
                    url=url,
                    content_type=content_type.value,
                    run_id=run_id,
                )

                try:
                    # Clean content
                    cleaned_content = clean(raw_content)

                    # Chunk content
                    chunks = chunk_document(
                        cleaned_content,
                        min_tokens=self.config.chunking.min_tokens,
                        max_tokens=self.config.chunking.max_tokens,
                        overlap_tokens=self.config.chunking.overlap_tokens,
                        document_title=Path(url).name,
                    )

                    if not chunks:
                        self.logger.warning("no_chunks_created", url=url, run_id=run_id)
                        continue

                    # Store document and chunks
                    if not dry_run and run_id:
                        document = Document(
                            source_url=url,
                            title=Path(url).name,
                            content_type=content_type,
                            raw_content=cleaned_content,
                            content_hash=chunks[0].content_hash if chunks else "",
                            language="en",
                            crawl_run_id=run_id,
                        )

                        stored_doc, is_new = self.storage.upsert_document(document)

                        # Convert ChunkResult to Chunk objects
                        if stored_doc.id:
                            chunk_objects = [
                                Chunk(
                                    content=chunk.content,
                                    content_hash=chunk.content_hash,
                                    chunk_index=chunk.chunk_index,
                                    heading_path=chunk.heading_path,
                                    token_count=chunk.token_count,
                                    document_id=stored_doc.id,
                                )
                                for chunk in chunks
                            ]
                            self.storage.insert_chunks(chunk_objects)

                        stats.documents_stored += 1
                        stats.chunks_created += len(chunks)
                        self.logger.info(
                            "document_processed",
                            url=url,
                            chunks=len(chunks),
                            run_id=run_id,
                        )
                    else:
                        stats.documents_stored += 1
                        stats.chunks_created += len(chunks)
                        self.logger.info(
                            "document_processed_dry_run",
                            url=url,
                            chunks=len(chunks),
                        )

                except Exception as e:
                    stats.errors += 1
                    self.logger.error(
                        "error_processing_url",
                        url=url,
                        error=str(e),
                        run_id=run_id,
                    )

            # Finalize run
            end_time = datetime.now(tz=timezone.utc)
            if not dry_run and run_id:
                status = (
                    CrawlStatus.COMPLETED
                    if stats.errors == 0
                    else CrawlStatus.FAILED
                )
                summary = {
                    "urls_crawled": stats.urls_crawled,
                    "documents_stored": stats.documents_stored,
                    "chunks_created": stats.chunks_created,
                    "errors": stats.errors,
                    "duration_seconds": stats.duration_seconds,
                }
                self.storage.complete_run(run_id, status, summary)
                self.logger.info(
                    "crawl_run_completed",
                    run_id=run_id,
                    status=status.value,
                )

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
        """Log summary statistics for the run.

        Args:
            stats: PipelineStats from the completed run.
        """
        self.logger.info(
            "pipeline_summary",
            run_id=stats.run_id,
            urls_crawled=stats.urls_crawled,
            documents_stored=stats.documents_stored,
            chunks_created=stats.chunks_created,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
        )
