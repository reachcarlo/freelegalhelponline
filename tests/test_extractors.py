"""Tests for LITIGAGENT ExtractorBase interface + ExtractorRegistry (L1.3)."""

from __future__ import annotations

import pytest

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry


# --- Concrete test extractor implementations ---


class StubPDFExtractor(FileExtractor):
    """Stub extractor for testing — handles PDFs."""

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in ("pdf",) or mime_type == "application/pdf"

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        return ExtractionResult(
            text=f"[PDF content of {filename}]",
            page_count=1,
            metadata={"extractor": "stub_pdf"},
        )

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf"}


class StubDocxExtractor(FileExtractor):
    """Stub extractor for testing — handles DOCX."""

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in ("docx",) or mime_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        return ExtractionResult(
            text=f"[DOCX content of {filename}]",
            metadata={"extractor": "stub_docx"},
        )

    @property
    def supported_extensions(self) -> set[str]:
        return {"docx"}


class StubTextExtractor(FileExtractor):
    """Stub extractor for testing — handles plain text."""

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in ("txt", "md") or mime_type.startswith("text/")

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        return ExtractionResult(
            text=file_bytes.decode("utf-8", errors="replace"),
            metadata={"extractor": "stub_text"},
        )

    @property
    def supported_extensions(self) -> set[str]:
        return {"txt", "md"}


# --- ExtractionResult Tests ---


class TestExtractionResult:
    def test_defaults(self):
        result = ExtractionResult(text="Hello")
        assert result.text == "Hello"
        assert result.page_count is None
        assert result.ocr_confidence is None
        assert result.metadata == {}
        assert result.warnings == []

    def test_all_fields(self):
        result = ExtractionResult(
            text="Extracted text",
            page_count=5,
            ocr_confidence=0.92,
            metadata={"language": "en"},
            warnings=["Page 3 had low contrast"],
        )
        assert result.page_count == 5
        assert result.ocr_confidence == 0.92
        assert result.metadata == {"language": "en"}
        assert result.warnings == ["Page 3 had low contrast"]

    def test_mutable_defaults_isolated(self):
        r1 = ExtractionResult(text="A")
        r2 = ExtractionResult(text="B")
        r1.metadata["key"] = "val"
        r1.warnings.append("warn")
        assert r2.metadata == {}
        assert r2.warnings == []


# --- FileExtractor ABC Tests ---


class TestFileExtractorABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            FileExtractor()  # type: ignore[abstract]

    def test_stub_implements_interface(self):
        ext = StubPDFExtractor()
        assert isinstance(ext, FileExtractor)

    def test_can_extract(self):
        ext = StubPDFExtractor()
        assert ext.can_extract("application/pdf", "pdf") is True
        assert ext.can_extract("text/plain", "txt") is False

    def test_extract_returns_result(self):
        ext = StubPDFExtractor()
        result = ext.extract(b"fake pdf bytes", "complaint.pdf")
        assert isinstance(result, ExtractionResult)
        assert "complaint.pdf" in result.text
        assert result.page_count == 1

    def test_supported_extensions(self):
        assert StubPDFExtractor().supported_extensions == {"pdf"}
        assert StubDocxExtractor().supported_extensions == {"docx"}
        assert StubTextExtractor().supported_extensions == {"txt", "md"}

    def test_partial_implementation_raises(self):
        """A subclass missing any abstract method cannot be instantiated."""

        class IncompleteExtractor(FileExtractor):
            def can_extract(self, mime_type: str, extension: str) -> bool:
                return False

            # Missing extract() and supported_extensions

        with pytest.raises(TypeError):
            IncompleteExtractor()  # type: ignore[abstract]


# --- ExtractorRegistry Tests ---


class TestExtractorRegistry:
    def test_empty_registry_returns_none(self):
        reg = ExtractorRegistry()
        assert reg.get_extractor("application/pdf", "pdf") is None

    def test_empty_registry_resolve_raises(self):
        reg = ExtractorRegistry()
        with pytest.raises(ValueError, match="No extractor registered"):
            reg.resolve("application/pdf", "pdf")

    def test_register_and_resolve(self):
        reg = ExtractorRegistry()
        pdf_ext = StubPDFExtractor()
        reg.register(pdf_ext)
        assert reg.resolve("application/pdf", "pdf") is pdf_ext

    def test_resolve_by_extension(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        result = reg.get_extractor("application/octet-stream", "pdf")
        assert result is not None
        assert isinstance(result, StubPDFExtractor)

    def test_resolve_by_mime_type(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        result = reg.get_extractor("application/pdf", "unknown")
        assert result is not None
        assert isinstance(result, StubPDFExtractor)

    def test_multiple_extractors(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        reg.register(StubDocxExtractor())
        reg.register(StubTextExtractor())

        assert isinstance(reg.resolve("application/pdf", "pdf"), StubPDFExtractor)
        assert isinstance(
            reg.resolve(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "docx",
            ),
            StubDocxExtractor,
        )
        assert isinstance(reg.resolve("text/plain", "txt"), StubTextExtractor)

    def test_first_match_wins(self):
        """If two extractors could handle the same type, the first registered wins."""
        reg = ExtractorRegistry()
        ext1 = StubTextExtractor()
        ext2 = StubTextExtractor()
        reg.register(ext1)
        reg.register(ext2)
        assert reg.resolve("text/plain", "txt") is ext1

    def test_extension_normalization(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        # Leading dot stripped, case normalized
        assert reg.get_extractor("application/pdf", ".PDF") is not None
        assert reg.get_extractor("application/pdf", ".pdf") is not None
        assert reg.get_extractor("application/pdf", "PDF") is not None

    def test_mime_type_normalization(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        assert reg.get_extractor("APPLICATION/PDF", "pdf") is not None

    def test_no_match_for_unknown_type(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        reg.register(StubDocxExtractor())
        assert reg.get_extractor("video/mp4", "mp4") is None

    def test_registered_extensions(self):
        reg = ExtractorRegistry()
        assert reg.registered_extensions == set()
        reg.register(StubPDFExtractor())
        assert reg.registered_extensions == {"pdf"}
        reg.register(StubTextExtractor())
        assert reg.registered_extensions == {"pdf", "txt", "md"}

    def test_registered_extensions_deduplication(self):
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        reg.register(StubPDFExtractor())
        assert reg.registered_extensions == {"pdf"}

    def test_resolve_error_message_includes_details(self):
        reg = ExtractorRegistry()
        with pytest.raises(ValueError, match="application/zip") as exc_info:
            reg.resolve("application/zip", "zip")
        assert "zip" in str(exc_info.value)

    def test_extract_through_registry(self):
        """End-to-end: register, resolve, extract."""
        reg = ExtractorRegistry()
        reg.register(StubPDFExtractor())
        reg.register(StubTextExtractor())

        ext = reg.resolve("text/plain", "txt")
        result = ext.extract(b"Hello, world!", "readme.txt")
        assert result.text == "Hello, world!"
        assert result.metadata["extractor"] == "stub_text"
