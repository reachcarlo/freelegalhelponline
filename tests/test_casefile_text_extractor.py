"""Tests for LITIGAGENT PlainTextExtractor (L1.6)."""

from __future__ import annotations

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.text import PlainTextExtractor


# --- Interface tests ---


class TestPlainTextExtractorInterface:
    def test_can_extract_txt_extension(self):
        assert PlainTextExtractor().can_extract("application/octet-stream", "txt") is True

    def test_can_extract_md_extension(self):
        assert PlainTextExtractor().can_extract("application/octet-stream", "md") is True

    def test_can_extract_rtf_extension(self):
        assert PlainTextExtractor().can_extract("application/octet-stream", "rtf") is True

    def test_can_extract_by_mime_text_plain(self):
        assert PlainTextExtractor().can_extract("text/plain", "unknown") is True

    def test_can_extract_by_mime_text_markdown(self):
        assert PlainTextExtractor().can_extract("text/markdown", "unknown") is True

    def test_can_extract_by_mime_text_rtf(self):
        assert PlainTextExtractor().can_extract("text/rtf", "unknown") is True

    def test_can_extract_by_mime_application_rtf(self):
        assert PlainTextExtractor().can_extract("application/rtf", "unknown") is True

    def test_cannot_extract_other(self):
        ext = PlainTextExtractor()
        assert ext.can_extract("application/pdf", "pdf") is False
        assert ext.can_extract("application/msword", "doc") is False
        assert ext.can_extract("image/png", "png") is False

    def test_supported_extensions(self):
        assert PlainTextExtractor().supported_extensions == {"txt", "md", "rtf"}

    def test_isinstance_file_extractor(self):
        assert isinstance(PlainTextExtractor(), FileExtractor)


# --- UTF-8 text extraction ---


class TestPlainTextUTF8:
    def test_simple_text(self):
        data = b"Hello, world!"
        result = PlainTextExtractor().extract(data, "test.txt")

        assert result.text == "Hello, world!"
        assert isinstance(result, ExtractionResult)
        assert result.metadata["extractor"] == "text"
        assert result.metadata["encoding"] == "utf-8"
        assert result.warnings == []

    def test_multiline_text(self):
        data = b"Line 1\nLine 2\nLine 3"
        result = PlainTextExtractor().extract(data, "multi.txt")

        assert "Line 1" in result.text
        assert "Line 2" in result.text
        assert "Line 3" in result.text

    def test_utf8_with_bom(self):
        data = b"\xef\xbb\xbfHello with BOM"
        result = PlainTextExtractor().extract(data, "bom.txt")

        assert "Hello with BOM" in result.text

    def test_unicode_characters(self):
        text = "Caf\u00e9 \u2014 na\u00efve r\u00e9sum\u00e9"
        data = text.encode("utf-8")
        result = PlainTextExtractor().extract(data, "unicode.txt")

        assert result.text == text
        assert result.metadata["encoding"] == "utf-8"

    def test_markdown_file(self):
        data = b"# Heading\n\nSome **bold** text.\n\n- item 1\n- item 2"
        result = PlainTextExtractor().extract(data, "readme.md")

        assert "# Heading" in result.text
        assert "**bold**" in result.text


# --- Encoding detection ---


class TestPlainTextEncodingDetection:
    def test_latin1_detected(self):
        text = "caf\u00e9 na\u00efve"
        data = text.encode("latin-1")
        result = PlainTextExtractor().extract(data, "latin.txt")

        assert "caf" in result.text
        assert result.metadata["encoding"] != "utf-8"

    def test_windows_1252_detected(self):
        # Windows-1252 smart quotes
        data = b"\x93Hello\x94 \x96 world"
        result = PlainTextExtractor().extract(data, "win.txt")

        assert result.text != ""
        assert result.metadata["encoding"] != "utf-8"


# --- Edge cases ---


class TestPlainTextEdgeCases:
    def test_empty_bytes(self):
        result = PlainTextExtractor().extract(b"", "empty.txt")

        assert result.text == ""
        assert any("No text extracted" in w for w in result.warnings)
        assert result.metadata["extractor"] == "text"

    def test_whitespace_only(self):
        result = PlainTextExtractor().extract(b"   \n\t\n  ", "spaces.txt")

        assert any("No text extracted" in w for w in result.warnings)

    def test_very_long_text(self):
        data = ("A" * 100_000).encode("utf-8")
        result = PlainTextExtractor().extract(data, "large.txt")

        assert len(result.text) == 100_000
        assert result.warnings == []

    def test_returns_extraction_result(self):
        result = PlainTextExtractor().extract(b"Test", "test.txt")
        assert isinstance(result, ExtractionResult)

    def test_null_bytes_preserved(self):
        data = b"before\x00after"
        result = PlainTextExtractor().extract(data, "null.txt")

        assert "before" in result.text
        assert "after" in result.text
