"""Tests for cross-source validation report generation.

Tests the ValidationReport dataclass, individual checks, and the
run_cross_source_validation() function against a seeded in-memory database.
"""

from __future__ import annotations

import json

import pytest

from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage
from employee_help.validation_report import (
    CheckResult,
    SourceStats,
    ValidationReport,
    run_cross_source_validation,
)


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path):
    """Create a Storage instance with a temp database."""
    db_path = str(tmp_path / "test.db")
    return Storage(db_path)


def _seed_statutory_source(storage: Storage) -> int:
    """Seed a statutory source with documents and chunks."""
    source = storage.create_source(Source(
        name="Labor Code",
        slug="labor_code",
        source_type=SourceType.STATUTORY_CODE,
        base_url="https://leginfo.legislature.ca.gov",
    ))

    run = storage.create_run(source_id=source.id)

    doc = Document(
        source_url="https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=LAB&sectionNum=200",
        title="Labor Code § 200",
        content_type=ContentType.HTML,
        raw_content="<html>Section 200 content</html>",
        content_hash="hash_lab_200",
        source_id=source.id,
        crawl_run_id=run.id,
    )
    doc, _ = storage.upsert_document(doc)

    chunks = []
    for i in range(5):
        chunks.append(Chunk(
            document_id=doc.id,
            content=f"Section content chunk {i} about wages and employment law.",
            heading_path=f"Division 1 > Part 1 > Chapter {i}",
            token_count=150 + i * 10,
            content_hash=f"chunk_hash_lab_{i}",
            chunk_index=i,
            content_category=ContentCategory.STATUTORY_CODE,
            citation=f"Cal. Lab. Code § {200 + i}",
        ))
    storage.insert_chunks(chunks)

    return source.id


def _seed_agency_source(storage: Storage) -> int:
    """Seed an agency guidance source."""
    source = storage.create_source(Source(
        name="DIR Guidance",
        slug="dir",
        source_type=SourceType.AGENCY,
        base_url="https://dir.ca.gov",
    ))

    run = storage.create_run(source_id=source.id)

    doc = Document(
        source_url="https://dir.ca.gov/dlse/faq.html",
        title="DIR FAQ",
        content_type=ContentType.HTML,
        raw_content="<html>FAQ content</html>",
        content_hash="hash_dir_faq",
        source_id=source.id,
        crawl_run_id=run.id,
    )
    doc, _ = storage.upsert_document(doc)

    chunks = []
    for i in range(3):
        chunks.append(Chunk(
            document_id=doc.id,
            content=f"FAQ answer {i} about employee rights.",
            heading_path=f"FAQ > Question {i}",
            token_count=100 + i * 20,
            content_hash=f"chunk_hash_dir_{i}",
            chunk_index=i,
            content_category=ContentCategory.AGENCY_GUIDANCE,
        ))
    storage.insert_chunks(chunks)

    return source.id


# ── DataClass Tests ────────────────────────────────────────


class TestCheckResult:
    def test_basic_check(self):
        check = CheckResult(name="test_check", passed=True, message="OK")
        assert check.passed is True
        assert check.name == "test_check"

    def test_failed_check_with_details(self):
        check = CheckResult(
            name="fail_check",
            passed=False,
            message="Failed",
            details={"reason": "missing data"},
        )
        assert check.passed is False
        assert check.details["reason"] == "missing data"


class TestValidationReport:
    def test_empty_report_passes(self):
        report = ValidationReport()
        assert report.passed is True
        assert report.checks_passed == 0
        assert report.checks_failed == 0

    def test_all_checks_pass(self):
        report = ValidationReport(checks=[
            CheckResult(name="a", passed=True, message="OK"),
            CheckResult(name="b", passed=True, message="OK"),
        ])
        assert report.passed is True
        assert report.checks_passed == 2
        assert report.checks_failed == 0

    def test_one_check_fails(self):
        report = ValidationReport(checks=[
            CheckResult(name="a", passed=True, message="OK"),
            CheckResult(name="b", passed=False, message="FAIL"),
        ])
        assert report.passed is False
        assert report.checks_passed == 1
        assert report.checks_failed == 1

    def test_to_json(self):
        report = ValidationReport(
            generated_at="2026-01-01T00:00:00Z",
            total_sources=2,
            checks=[CheckResult(name="a", passed=True, message="OK")],
        )
        data = json.loads(report.to_json())
        assert data["total_sources"] == 2
        assert data["summary"]["overall_status"] == "PASS"
        assert data["summary"]["passed"] == 1

    def test_to_markdown(self):
        report = ValidationReport(
            generated_at="2026-01-01T00:00:00Z",
            total_sources=1,
            total_chunks=10,
            total_active_chunks=8,
            sources=[
                SourceStats(
                    slug="labor_code",
                    name="Labor Code",
                    source_type="statutory_code",
                    document_count=5,
                    chunk_count=10,
                    active_chunks=8,
                    inactive_chunks=2,
                    avg_tokens_per_chunk=200.0,
                    min_tokens=50,
                    max_tokens=500,
                    citations_present=10,
                ),
            ],
            checks=[CheckResult(name="test", passed=True, message="OK")],
        )
        md = report.to_markdown()
        assert "# Cross-Source Validation Report" in md
        assert "labor_code" in md
        assert "**[PASS]**" in md

    def test_to_markdown_with_failed_checks(self):
        report = ValidationReport(
            checks=[CheckResult(name="test", passed=False, message="BAD")],
        )
        md = report.to_markdown()
        assert "**[FAIL]**" in md

    def test_to_markdown_with_citation_samples(self):
        report = ValidationReport(
            citation_samples=[{
                "citation": "Cal. Lab. Code § 200",
                "code": "Cal. Lab. Code",
                "section_num": "200",
                "valid": True,
            }],
        )
        md = report.to_markdown()
        assert "Cal. Lab. Code § 200" in md
        assert "## Citation Samples" in md


# ── Integration Tests ──────────────────────────────────────


class TestRunCrossSourceValidation:
    def test_empty_database(self, storage):
        """Validation on empty DB produces report with no sources."""
        report = run_cross_source_validation(storage)
        assert report.total_sources == 0
        assert report.total_documents == 0
        assert report.total_chunks == 0

    def test_single_statutory_source(self, storage):
        """Validation with one statutory source runs all checks."""
        _seed_statutory_source(storage)

        report = run_cross_source_validation(storage, citation_sample_size=3)
        assert report.total_sources == 1
        assert report.total_documents == 1
        assert report.total_chunks == 5
        assert report.total_active_chunks == 5

        # Check that source stats were collected
        assert len(report.sources) == 1
        assert report.sources[0].slug == "labor_code"
        assert report.sources[0].document_count == 1
        assert report.sources[0].chunk_count == 5
        assert report.sources[0].citations_present == 5

        # Checks should include: has_content, has_citations, correct_category, token_bounds
        check_names = [c.name for c in report.checks]
        assert "labor_code_has_content" in check_names
        assert "labor_code_has_citations" in check_names
        assert "labor_code_correct_category" in check_names
        assert "labor_code_token_bounds" in check_names

    def test_agency_source_no_citation_checks(self, storage):
        """Agency sources should not have citation checks."""
        _seed_agency_source(storage)

        report = run_cross_source_validation(storage)
        check_names = [c.name for c in report.checks]
        assert "dir_has_content" in check_names
        # No citation or category checks for agency sources
        assert "dir_has_citations" not in check_names
        assert "dir_correct_category" not in check_names

    def test_multiple_sources(self, storage):
        """Validation with multiple sources."""
        _seed_statutory_source(storage)
        _seed_agency_source(storage)

        report = run_cross_source_validation(storage)
        assert report.total_sources == 2
        assert report.total_documents == 2
        assert report.total_chunks == 8  # 5 + 3

    def test_citation_format_validation(self, storage):
        """Citation samples are validated against expected format."""
        _seed_statutory_source(storage)

        report = run_cross_source_validation(storage, citation_sample_size=5)

        # All citations should match "Cal. ... Code § NNN" format
        citation_check = next(
            (c for c in report.checks if c.name == "citation_format_validation"),
            None,
        )
        assert citation_check is not None
        assert citation_check.passed is True

        # Should have sampled citations
        assert len(report.citation_samples) == 5
        assert all(s["valid"] for s in report.citation_samples)

    def test_no_empty_chunks_check(self, storage):
        """No empty chunks check passes with valid data."""
        _seed_statutory_source(storage)

        report = run_cross_source_validation(storage)
        empty_check = next(
            (c for c in report.checks if c.name == "no_empty_chunks"), None
        )
        assert empty_check is not None
        assert empty_check.passed is True

    def test_cross_source_duplicates_tracked(self, storage):
        """Cross-source duplicates are reported."""
        _seed_statutory_source(storage)
        _seed_agency_source(storage)

        report = run_cross_source_validation(storage)
        dup_check = next(
            (c for c in report.checks if c.name == "cross_source_duplicates"), None
        )
        assert dup_check is not None
        # No duplicates with our test data (different hashes)
        assert report.cross_source_duplicates == 0

    def test_token_bounds_check(self, storage):
        """Token bounds check passes when all chunks are within limits."""
        _seed_statutory_source(storage)

        report = run_cross_source_validation(storage)
        bounds_check = next(
            (c for c in report.checks if c.name == "labor_code_token_bounds"), None
        )
        assert bounds_check is not None
        assert bounds_check.passed is True

    def test_report_serialization_roundtrip(self, storage):
        """Report can be serialized to JSON and contains all expected fields."""
        _seed_statutory_source(storage)
        _seed_agency_source(storage)

        report = run_cross_source_validation(storage, citation_sample_size=3)

        json_str = report.to_json()
        data = json.loads(json_str)

        assert "generated_at" in data
        assert "total_sources" in data
        assert "sources" in data
        assert "checks" in data
        assert "summary" in data
        assert data["summary"]["overall_status"] in ("PASS", "FAIL")
