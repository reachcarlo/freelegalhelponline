"""Tests for the pipeline orchestration module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

from employee_help.config import CrawlConfig, ChunkingConfig, SourceConfig, StatutoryConfig, ExtractionConfig
from employee_help.pipeline import Pipeline, PipelineStats
from employee_help.scraper.crawler import CrawlResult, UrlClassification
from employee_help.storage.models import ContentCategory, ContentType, SourceType


@pytest.fixture
def test_config() -> CrawlConfig:
    """Create a test configuration."""
    return CrawlConfig(
        seed_urls=["https://example.com"],
        allowlist_patterns=["example\\.com"],
        blocklist_patterns=[],
        rate_limit_seconds=0.1,
        max_pages=10,
        chunking=ChunkingConfig(min_tokens=100, max_tokens=1000, overlap_tokens=50),
        database_path=":memory:",  # Use in-memory SQLite for testing
    )


@pytest.fixture
def pipeline(test_config: CrawlConfig) -> Pipeline:
    """Create a test pipeline."""
    return Pipeline(test_config)


class TestPipelineInitialization:
    """Tests for pipeline initialization."""

    def test_pipeline_initializes_with_config(self, test_config: CrawlConfig) -> None:
        """Pipeline should initialize with a config."""
        pipeline = Pipeline(test_config)
        assert pipeline.config == test_config
        assert pipeline.storage is not None
        assert pipeline.crawler is not None

    def test_pipeline_creates_database(self, test_config: CrawlConfig) -> None:
        """Pipeline should create a database file if path is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = CrawlConfig(
                seed_urls=test_config.seed_urls,
                allowlist_patterns=test_config.allowlist_patterns,
                blocklist_patterns=test_config.blocklist_patterns,
                rate_limit_seconds=test_config.rate_limit_seconds,
                max_pages=test_config.max_pages,
                chunking=test_config.chunking,
                database_path=str(db_path),
            )
            pipeline = Pipeline(config)
            assert pipeline.storage is not None
            pipeline.storage.close()


class TestPipelineStats:
    """Tests for PipelineStats dataclass."""

    def test_pipeline_stats_duration_calculation(self) -> None:
        """Duration should be calculated correctly."""
        from datetime import datetime, timezone, timedelta

        start = datetime.now(tz=timezone.utc)
        end = start + timedelta(seconds=5)

        stats = PipelineStats(
            run_id=1,
            urls_crawled=10,
            documents_stored=5,
            chunks_created=50,
            errors=0,
            start_time=start,
            end_time=end,
        )

        assert stats.duration_seconds == 5.0

    def test_pipeline_stats_with_errors(self) -> None:
        """Stats should track errors correctly."""
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=1,
            urls_crawled=10,
            documents_stored=5,
            chunks_created=50,
            errors=3,
            start_time=now,
            end_time=now,
        )

        assert stats.errors == 3


class TestPipelineRun:
    """Tests for pipeline execution."""

    def test_pipeline_dry_run_skips_storage(
        self, pipeline: Pipeline
    ) -> None:
        """Dry run should not store to database."""
        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    mock_crawl.return_value = []
                    stats = pipeline.run(dry_run=True)

                    assert stats.urls_crawled == 0
                    assert stats.documents_stored == 0
                    assert stats.run_id == -1  # No run created in dry-run mode

    def test_pipeline_handles_empty_crawl_result(
        self, pipeline: Pipeline
    ) -> None:
        """Pipeline should handle crawls with no results."""
        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    mock_crawl.return_value = []
                    stats = pipeline.run(dry_run=True)

                    assert stats.urls_crawled == 0
                    assert stats.documents_stored == 0
                    assert stats.errors == 0

    def test_pipeline_skips_crawl_errors(
        self, pipeline: Pipeline
    ) -> None:
        """Pipeline should skip URLs with crawl errors."""
        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    # Create a crawl result with an error
                    result = CrawlResult(
                        url="https://example.com/error",
                        classification=UrlClassification.IN_SCOPE,
                        error="Connection failed",
                    )
                    mock_crawl.return_value = [result]

                    stats = pipeline.run(dry_run=True)

                    assert stats.urls_crawled == 1
                    assert stats.documents_stored == 0
                    assert stats.errors == 1

    def test_pipeline_closes_crawler_on_completion(
        self, pipeline: Pipeline
    ) -> None:
        """Pipeline should close the crawler after run."""
        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "close") as mock_close:
                    with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                        mock_crawl.return_value = []
                        pipeline.run(dry_run=True)
                        mock_close.assert_called_once()

    def test_pipeline_closes_crawler_on_exception(
        self, pipeline: Pipeline
    ) -> None:
        """Pipeline should close the crawler even if an exception occurs."""
        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "close") as mock_close:
                    with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                        mock_crawl.side_effect = RuntimeError("Test error")
                        with pytest.raises(RuntimeError):
                            pipeline.run(dry_run=True)
                        mock_close.assert_called_once()


class TestPipelineWithRealStorage:
    """Tests for pipeline with real (in-memory) storage."""

    def test_pipeline_creates_run_record(self, test_config: CrawlConfig) -> None:
        """Pipeline should create a run record in the database."""
        pipeline = Pipeline(test_config)

        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    mock_crawl.return_value = []
                    stats = pipeline.run(dry_run=False)

                    assert stats.run_id > 0
                    run_info = pipeline.storage.get_run_summary(stats.run_id)
                    assert run_info is not None
                    assert run_info["status"] == "completed"

    def test_pipeline_stores_document_and_chunks(
        self, test_config: CrawlConfig
    ) -> None:
        """Pipeline should store documents and chunks in the database."""
        from employee_help.scraper.extractors.html import extract_html

        pipeline = Pipeline(test_config)

        # Create a simple HTML result
        html_content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is test content for the pipeline.</p>
        </body>
        </html>
        """

        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    result = CrawlResult(
                        url="https://example.com/test",
                        html=html_content,
                        classification=UrlClassification.IN_SCOPE,
                        status_code=200,
                    )
                    mock_crawl.return_value = [result]

                    stats = pipeline.run(dry_run=False)

                    assert stats.urls_crawled == 1
                    assert stats.documents_stored == 1
                    assert stats.chunks_created > 0
                    assert stats.errors == 0

                    # Verify document was stored
                    doc = pipeline.storage.get_document_by_url("https://example.com/test")
                    assert doc is not None
                    assert doc.source_url == "https://example.com/test"

                    # Verify chunks were stored
                    chunks = pipeline.storage.get_chunks_for_document(doc.id)
                    assert len(chunks) > 0

    def test_pipeline_with_pdf_content(
        self, test_config: CrawlConfig
    ) -> None:
        """Pipeline should handle PDF content correctly."""
        pipeline = Pipeline(test_config)

        # Create a minimal PDF-like content
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\ntrail\n"

        with patch.object(pipeline.crawler, "start"):
            with patch.object(pipeline.crawler, "stop"):
                with patch.object(pipeline.crawler, "crawl") as mock_crawl:
                    with patch("employee_help.scraper.extractors.pdf.extract_pdf") as mock_extract:
                        # Mock PDF extraction to return a result
                        from employee_help.scraper.extractors.pdf import PdfExtractionResult
                        mock_extract.return_value = PdfExtractionResult(
                            title="Test PDF",
                            markdown="# Test PDF\n\nTest content",
                            headings=["Test PDF"],
                            source_url="https://example.com/test.pdf",
                            page_count=1,
                        )

                        result = CrawlResult(
                            url="https://example.com/test.pdf",
                            pdf_bytes=pdf_content,
                            classification=UrlClassification.PDF_DOWNLOAD,
                            status_code=200,
                        )
                        mock_crawl.return_value = [result]

                        stats = pipeline.run(dry_run=False)

                        assert stats.urls_crawled == 1
                        assert stats.documents_stored == 1
                        assert stats.chunks_created > 0
                        assert stats.errors == 0


class TestCACIPipelineRouting:
    """Tests for CACI PDF pipeline routing."""

    def _make_caci_source_config(self) -> SourceConfig:
        """Create a SourceConfig for CACI with caci_pdf method."""
        return SourceConfig(
            name="CACI Jury Instructions (Employment)",
            slug="caci",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://www.courts.ca.gov/partners/317.htm",
            extraction=ExtractionConfig(content_category="jury_instruction"),
            chunking=ChunkingConfig(
                min_tokens=50, max_tokens=1500, overlap_tokens=100,
                strategy="section_boundary",
            ),
            statutory=StatutoryConfig(
                code_abbreviation="CACI",
                code_name="CACI Jury Instructions",
                citation_prefix="CACI No.",
                method="caci_pdf",
            ),
            database_path=":memory:",
        )

    def test_caci_pdf_routes_to_statutory_pipeline(self):
        """Pipeline with caci_pdf method should route to _run_statutory."""
        config = self._make_caci_source_config()
        pipeline = Pipeline(config)

        # Verify it's treated as statutory (no crawler)
        assert pipeline.crawler is None

    def test_caci_pdf_method_dispatches_correctly(self):
        """_run_statutory should call _extract_via_caci_pdf for caci_pdf method."""
        from employee_help.scraper.extractors.statute import StatuteSection, HierarchyPath

        config = self._make_caci_source_config()
        pipeline = Pipeline(config)

        mock_section = StatuteSection(
            section_number="2430",
            code_abbreviation="CACI",
            text="Test instruction text.",
            citation="CACI No. 2430",
            hierarchy=HierarchyPath(code_name="CACI"),
            source_url="https://www.courts.ca.gov/partners/317.htm",
        )

        with patch.object(pipeline, "_extract_via_caci_pdf", return_value=[mock_section]) as mock_extract:
            stats = pipeline.run(dry_run=False)

            mock_extract.assert_called_once()
            assert stats.documents_stored == 1
            assert stats.chunks_created >= 1

    def test_caci_pipeline_uses_jury_instruction_category(self):
        """CACI pipeline should store chunks with jury_instruction category."""
        from employee_help.scraper.extractors.statute import StatuteSection, HierarchyPath

        config = self._make_caci_source_config()
        pipeline = Pipeline(config)

        mock_section = StatuteSection(
            section_number="2430",
            code_abbreviation="CACI",
            text="Test instruction text for chunking.",
            citation="CACI No. 2430",
            hierarchy=HierarchyPath(code_name="CACI"),
            source_url="https://www.courts.ca.gov/partners/317.htm",
        )

        with patch.object(pipeline, "_extract_via_caci_pdf", return_value=[mock_section]):
            pipeline.run(dry_run=False)

        # Verify the stored chunks have jury_instruction category
        source = pipeline.storage.get_source("caci")
        assert source is not None
        docs = pipeline.storage.get_all_documents(source_id=source.id)
        assert len(docs) > 0

        chunks = pipeline.storage.get_chunks_for_document(docs[0].id)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content_category == ContentCategory.JURY_INSTRUCTION
