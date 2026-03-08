"""Tests for LITIGAGENT PDFExtractor (L1.4)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.pdf import PDFExtractor


# --- Helpers ---


def _make_page(text: str | None = None) -> MagicMock:
    """Create a mock pdfplumber page with given extracted text."""
    page = MagicMock()
    page.extract_text.return_value = text
    return page


def _make_pdf_context(pages: list[MagicMock]) -> MagicMock:
    """Create a mock for pdfplumber.open() context manager."""
    pdf = MagicMock()
    pdf.pages = pages
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


def _mock_ocr_data(words_and_confs: list[tuple[str, int]]) -> dict:
    """Build pytesseract image_to_data return value."""
    return {
        "text": [w for w, _ in words_and_confs],
        "conf": [c for _, c in words_and_confs],
    }


# Text long enough to pass the default min_text_density (50 chars).
_LONG_TEXT = "This is a test document with enough text to pass the density check easily."


# --- Interface tests ---


class TestPDFExtractorInterface:
    def test_can_extract_by_extension(self):
        assert PDFExtractor().can_extract("application/octet-stream", "pdf") is True

    def test_can_extract_by_mime(self):
        assert PDFExtractor().can_extract("application/pdf", "unknown") is True

    def test_cannot_extract_other(self):
        ext = PDFExtractor()
        assert ext.can_extract("application/msword", "docx") is False
        assert ext.can_extract("text/plain", "txt") is False

    def test_supported_extensions(self):
        assert PDFExtractor().supported_extensions == {"pdf"}

    def test_isinstance_file_extractor(self):
        assert isinstance(PDFExtractor(), FileExtractor)


# --- Text extraction (no OCR needed) ---


class TestPDFTextExtraction:
    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_single_page_text(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page(_LONG_TEXT)])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "test.pdf")

        assert result.text == _LONG_TEXT
        assert result.page_count == 1
        assert result.ocr_confidence is None
        assert result.metadata["extractor"] == "pdf"
        assert "ocr_used" not in result.metadata
        assert result.warnings == []

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_multi_page_text(self, mock_pdfplumber):
        texts = [
            "Page one has plenty of text content to be extracted natively by pdfplumber.",
            "Page two also contains sufficient characters for native text extraction mode.",
            "Page three rounds out this document with even more readable text content here.",
        ]
        pdf_ctx = _make_pdf_context([_make_page(t) for t in texts])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "multi.pdf")

        assert result.page_count == 3
        for t in texts:
            assert t in result.text
        assert result.ocr_confidence is None
        assert result.warnings == []

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_pages_joined_with_form_feed(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page("A" * 60), _make_page("B" * 60)])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "joined.pdf")

        parts = result.text.split("\f")
        assert len(parts) == 2

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_none_text_treated_as_empty(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page(None)])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor(ocr_enabled=False).extract(b"fake", "none.pdf")

        assert result.text == ""
        assert len(result.warnings) == 1

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_returns_extraction_result(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page(_LONG_TEXT)])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "test.pdf")

        assert isinstance(result, ExtractionResult)


# --- OCR disabled ---


class TestPDFOCRDisabled:
    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_empty_page_no_ocr_warns(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page("")])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor(ocr_enabled=False).extract(b"fake", "empty.pdf")

        assert result.text == ""
        assert any("no text extracted" in w for w in result.warnings)
        assert any("enable OCR" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    def test_sparse_text_kept_when_ocr_disabled(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page("Hi")])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor(ocr_enabled=False).extract(b"fake", "sparse.pdf")

        assert result.text == "Hi"


# --- OCR fallback ---


class TestPDFOCRFallback:
    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_scanned_page_triggers_ocr(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("Hello", 95), ("world", 90), ("", -1), ("test", 88),
        ])

        result = PDFExtractor().extract(b"fake", "scanned.pdf")

        assert "Hello" in result.text
        assert "world" in result.text
        assert "test" in result.text
        assert result.ocr_confidence is not None
        assert result.ocr_confidence > 0.85
        assert result.metadata["ocr_used"] is True
        assert result.metadata["ocr_page_count"] == 1

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_ocr_confidence_average(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("word1", 80), ("word2", 60), ("word3", 70),
        ])

        result = PDFExtractor().extract(b"fake", "low.pdf")

        expected = (80 + 60 + 70) / 3 / 100.0
        assert result.ocr_confidence == pytest.approx(expected)

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_low_confidence_warning(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("blurry", 50), ("text", 40),
        ])

        result = PDFExtractor().extract(b"fake", "blurry.pdf")

        assert any("low OCR confidence" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_high_confidence_no_warning(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("clear", 95), ("text", 92), ("here", 90),
        ])

        result = PDFExtractor().extract(b"fake", "clear.pdf")

        assert result.ocr_confidence is not None
        assert result.ocr_confidence > 0.85
        assert not any("low OCR confidence" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract", None)
    def test_pytesseract_not_installed(self, mock_pdfplumber):
        pdf_ctx = _make_pdf_context([_make_page("")])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "no_ocr.pdf")

        assert result.text == ""
        assert any("OCR failed or unavailable" in w for w in result.warnings)
        assert result.ocr_confidence is None

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_ocr_exception_handled(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.side_effect = RuntimeError("render failed")
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        result = PDFExtractor().extract(b"fake", "broken.pdf")

        assert result.text == ""
        assert any("OCR failed or unavailable" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_ocr_empty_result(self, mock_tess, mock_pdfplumber):
        """OCR runs but produces no recognizable words."""
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("", -1)])

        result = PDFExtractor().extract(b"fake", "blank.pdf")

        assert result.text == ""
        assert any("OCR failed or unavailable" in w for w in result.warnings)


# --- Mixed pages ---


class TestPDFMixedPages:
    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_text_and_scanned_mixed(self, mock_tess, mock_pdfplumber):
        text_page = _make_page(_LONG_TEXT)
        scanned_page = _make_page("")
        scanned_page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([text_page, scanned_page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("OCR", 90), ("result", 85),
        ])

        result = PDFExtractor().extract(b"fake", "mixed.pdf")

        assert result.page_count == 2
        assert _LONG_TEXT in result.text
        assert "OCR" in result.text
        assert result.ocr_confidence is not None
        assert result.metadata["ocr_used"] is True
        assert result.metadata["ocr_page_count"] == 1

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_multiple_scanned_pages_average_confidence(self, mock_tess, mock_pdfplumber):
        pages = [_make_page(""), _make_page("")]
        for p in pages:
            p.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context(pages)
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        # First call: 90%, second call: 70%
        mock_tess.image_to_data.side_effect = [
            _mock_ocr_data([("page1", 90)]),
            _mock_ocr_data([("page2", 70)]),
        ]

        result = PDFExtractor().extract(b"fake", "two_scanned.pdf")

        expected = (0.90 + 0.70) / 2
        assert result.ocr_confidence == pytest.approx(expected)
        assert result.metadata["ocr_page_count"] == 2
        # Only page 2 (70%) should have low confidence warning
        low_warnings = [w for w in result.warnings if "low OCR confidence" in w]
        assert len(low_warnings) == 1
        assert "Page 2" in low_warnings[0]


# --- Custom configuration ---


class TestPDFExtractorConfig:
    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_custom_min_text_density(self, mock_tess, mock_pdfplumber):
        """Higher density threshold triggers OCR on pages with some text."""
        page = _make_page("Short text")  # 10 chars, below custom threshold of 100
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("OCR", 95)])

        result = PDFExtractor(min_text_density=100).extract(b"fake", "custom.pdf")

        assert "OCR" in result.text
        assert result.metadata.get("ocr_used") is True

    @patch("employee_help.casefile.extractors.pdf.pdfplumber")
    @patch("employee_help.casefile.extractors.pdf._pytesseract")
    def test_custom_ocr_resolution(self, mock_tess, mock_pdfplumber):
        page = _make_page("")
        page.to_image.return_value.original = MagicMock()
        pdf_ctx = _make_pdf_context([page])
        mock_pdfplumber.open.return_value = pdf_ctx

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("hi", 90)])

        PDFExtractor(ocr_resolution=600).extract(b"fake", "hires.pdf")

        page.to_image.assert_called_once_with(resolution=600)
