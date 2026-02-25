"""Tests for the validation module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from employee_help.config import CrawlConfig, ChunkingConfig
from employee_help.pipeline import PipelineStats
from employee_help.storage.models import Chunk, Document, ContentType
from employee_help.validation import Validator, ValidationReport, ChunkSample
from datetime import datetime, timezone


@pytest.fixture
def test_config_path() -> str:
    """Create a temporary test configuration."""
    config_data = {
        "seed_urls": ["https://example.com"],
        "allowlist_patterns": ["example\\.com"],
        "blocklist_patterns": [],
        "rate_limit_seconds": 0.1,
        "max_pages": 10,
        "chunking": {
            "min_tokens": 100,
            "max_tokens": 1000,
            "overlap_tokens": 50,
        },
        "database_path": ":memory:",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        return f.name


class TestChunkSample:
    """Tests for ChunkSample dataclass."""

    def test_chunk_sample_creation(self) -> None:
        """ChunkSample should store all required fields."""
        sample = ChunkSample(
            chunk_id=1,
            document_id=1,
            source_url="https://example.com/test",
            heading_path="Section > Subsection",
            token_count=250,
            content_preview="This is a preview of the chunk content...",
        )

        assert sample.chunk_id == 1
        assert sample.token_count == 250
        assert "preview" in sample.content_preview


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_validation_report_to_json(self) -> None:
        """ValidationReport should serialize to JSON."""
        report = ValidationReport(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            run1_stats={"urls_crawled": 5, "documents_stored": 3},
            run2_stats={"urls_crawled": 5, "documents_stored": 0},
            idempotency_check={"idempotent": "YES"},
            data_quality_metrics={"total_documents": 3},
            chunk_samples=[],
            coverage_percent=80.0,
            validation_status="PASS",
            notes=[],
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["validation_status"] == "PASS"
        assert parsed["coverage_percent"] == 80.0

    def test_validation_report_to_markdown(self) -> None:
        """ValidationReport should serialize to Markdown."""
        report = ValidationReport(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            run1_stats={"urls_crawled": 5, "documents_stored": 3},
            run2_stats={"urls_crawled": 5, "documents_stored": 0},
            idempotency_check={"idempotent": "YES"},
            data_quality_metrics={"total_documents": 3},
            chunk_samples=[],
            coverage_percent=80.0,
            validation_status="PASS",
            notes=["All checks passed"],
        )

        markdown = report.to_markdown()
        assert "# Phase 1G Validation Report" in markdown
        assert "PASS" in markdown
        assert "All checks passed" in markdown


class TestValidator:
    """Tests for the Validator class."""

    def test_validator_initialization(self, test_config_path: str) -> None:
        """Validator should initialize with config."""
        validator = Validator(test_config_path)
        assert validator.config is not None
        assert validator.storage is not None
        validator.close()

    def test_stats_to_dict_conversion(self, test_config_path: str) -> None:
        """Validator should convert PipelineStats to dict."""
        validator = Validator(test_config_path)

        stats = PipelineStats(
            run_id=1,
            urls_crawled=10,
            documents_stored=5,
            chunks_created=50,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        result = validator._stats_to_dict(stats)
        assert result["urls_crawled"] == 10
        assert result["documents_stored"] == 5
        assert result["chunks_created"] == 50
        validator.close()

    def test_analyze_idempotency(self, test_config_path: str) -> None:
        """Validator should analyze idempotency correctly."""
        validator = Validator(test_config_path)

        stats1 = PipelineStats(
            run_id=1,
            urls_crawled=10,
            documents_stored=5,
            chunks_created=50,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        # Idempotent run should store 0 new documents
        stats2 = PipelineStats(
            run_id=2,
            urls_crawled=10,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        result = validator._analyze_idempotency(stats1, stats2)
        assert result["idempotent"] == "YES"
        validator.close()

    def test_analyze_data_quality_empty(self, test_config_path: str) -> None:
        """Validator should handle empty database."""
        validator = Validator(test_config_path)

        result = validator._analyze_data_quality()
        assert result["total_documents"] == 0
        assert result["total_chunks"] == 0
        validator.close()

    def test_determine_status_pass(self, test_config_path: str) -> None:
        """Validator should determine PASS status."""
        validator = Validator(test_config_path)

        stats1 = PipelineStats(
            run_id=1,
            urls_crawled=10,
            documents_stored=5,
            chunks_created=50,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        stats2 = PipelineStats(
            run_id=2,
            urls_crawled=10,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        idempotency = {"idempotent": "YES"}
        quality = {"total_documents": 5, "total_chunks": 50}

        status = validator._determine_status(stats1, stats2, idempotency, quality)
        assert status == "PASS"
        validator.close()

    def test_determine_status_fail_no_crawl(self, test_config_path: str) -> None:
        """Validator should determine FAIL if crawl failed."""
        validator = Validator(test_config_path)

        stats1 = PipelineStats(
            run_id=1,
            urls_crawled=0,
            documents_stored=0,
            chunks_created=0,
            errors=1,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        stats2 = PipelineStats(
            run_id=2,
            urls_crawled=0,
            documents_stored=0,
            chunks_created=0,
            errors=0,
            start_time=datetime.now(tz=timezone.utc),
            end_time=datetime.now(tz=timezone.utc),
        )

        idempotency = {"idempotent": "YES"}
        quality = {"total_documents": 0, "total_chunks": 0}

        status = validator._determine_status(stats1, stats2, idempotency, quality)
        assert status == "FAIL"
        validator.close()

    def test_validator_context_manager(self, test_config_path: str) -> None:
        """Validator should work as context manager."""
        with Validator(test_config_path) as validator:
            assert validator.config is not None
            assert validator.storage is not None


class TestValidationIntegration:
    """Integration tests for validation workflow."""

    def test_run_validation_with_empty_database(self, test_config_path: str) -> None:
        """Validation should handle empty database gracefully."""
        with patch("employee_help.validation.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline_class.return_value = mock_pipeline

            now = datetime.now(tz=timezone.utc)
            stats = PipelineStats(
                run_id=1,
                urls_crawled=0,
                documents_stored=0,
                chunks_created=0,
                errors=0,
                start_time=now,
                end_time=now,
            )
            mock_pipeline.run.return_value = stats

            with Validator(test_config_path) as validator:
                report = validator.run_validation()

                assert report.validation_status == "FAIL"
                assert report.run1_stats["urls_crawled"] == 0
