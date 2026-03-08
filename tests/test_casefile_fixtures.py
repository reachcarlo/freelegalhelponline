"""Tests using casefile fixtures — validates extractors against realistic case documents."""

from pathlib import Path

import pytest

from employee_help.casefile.extractors.registry import ExtractorRegistry
from employee_help.casefile.extractors.text import PlainTextExtractor
from employee_help.casefile.extractors.email import EmailExtractor
from employee_help.casefile.processing import get_file_type, get_registry, content_hash

FIXTURES = Path(__file__).parent / "fixtures" / "casefile"


class TestFixtureExtraction:
    """End-to-end extraction tests using realistic fixture files."""

    def test_notes_txt_extraction(self):
        data = (FIXTURES / "notes.txt").read_bytes()
        ext = PlainTextExtractor()
        result = ext.extract(data, "notes.txt")
        assert "Johnson v. Acme Corp" in result.text
        assert "Age discrimination under FEHA" in result.text
        assert "Labor Code 1198.5" in result.text
        assert result.page_count is None  # plain text has no pages

    def test_email_eml_extraction(self):
        data = (FIXTURES / "email.eml").read_bytes()
        ext = EmailExtractor()
        result = ext.extract(data, "email.eml")
        assert "Restructuring Plan" in result.text
        assert "manager@acmecorp.example.com" in result.text
        assert "Senior Engineer - Sacramento" in result.text

    def test_performance_review_extraction(self):
        data = (FIXTURES / "performance_review.txt").read_bytes()
        ext = PlainTextExtractor()
        result = ext.extract(data, "performance_review.txt")
        assert "Exceeds Expectations" in result.text
        assert "David Johnson" in result.text
        assert "4.2 / 5.0" in result.text

    def test_termination_letter_extraction(self):
        data = (FIXTURES / "termination_letter.txt").read_bytes()
        ext = PlainTextExtractor()
        result = ext.extract(data, "termination_letter.txt")
        assert "Position Elimination" in result.text
        assert "November 15, 2025" in result.text
        assert "Severance" in result.text


class TestRegistryWithFixtures:
    """Registry resolution and extraction with fixture files."""

    def test_registry_resolves_txt(self):
        registry = get_registry()
        extractor = registry.get_extractor("text/plain", "txt")
        assert extractor is not None
        data = (FIXTURES / "notes.txt").read_bytes()
        result = extractor.extract(data, "notes.txt")
        assert len(result.text) > 100

    def test_registry_resolves_eml(self):
        registry = get_registry()
        extractor = registry.get_extractor("message/rfc822", "eml")
        assert extractor is not None
        data = (FIXTURES / "email.eml").read_bytes()
        result = extractor.extract(data, "email.eml")
        assert len(result.text) > 50

    def test_registry_resolves_all_fixture_types(self):
        """Verify the registry can resolve extractors for all fixture file types."""
        mime_map = {"txt": "text/plain", "eml": "message/rfc822"}
        registry = get_registry()
        for fixture_file in FIXTURES.iterdir():
            if fixture_file.is_file():
                ext = fixture_file.suffix.lstrip(".")
                mime = mime_map.get(ext, f"application/{ext}")
                extractor = registry.get_extractor(mime, ext)
                assert extractor is not None, f"No extractor for .{ext}"


class TestFileTypeMapping:
    """Verify file type detection for fixture files."""

    def test_txt_file_type(self):
        assert get_file_type("txt") is not None
        assert get_file_type("txt").value == "txt"

    def test_eml_file_type(self):
        assert get_file_type("eml") is not None
        assert get_file_type("eml").value == "eml"


class TestContentHashing:
    """Content hash consistency with fixture data."""

    def test_fixture_hash_deterministic(self):
        text = (FIXTURES / "notes.txt").read_text()
        h1 = content_hash(text)
        h2 = content_hash(text)
        assert h1 == h2

    def test_different_fixtures_different_hashes(self):
        notes = content_hash((FIXTURES / "notes.txt").read_text())
        review = content_hash((FIXTURES / "performance_review.txt").read_text())
        letter = content_hash((FIXTURES / "termination_letter.txt").read_text())
        assert len({notes, review, letter}) == 3
