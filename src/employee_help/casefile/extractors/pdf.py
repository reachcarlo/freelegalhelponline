"""PDFExtractor — text extraction with OCR fallback for scanned pages."""

from __future__ import annotations

import io
import logging

import pdfplumber

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

logger = logging.getLogger(__name__)

try:
    import pytesseract as _pytesseract  # type: ignore[import-untyped]
except ImportError:
    _pytesseract = None  # type: ignore[assignment]

# Minimum characters per page to consider it "text-based" (not scanned).
_MIN_TEXT_DENSITY = 50


class PDFExtractor(FileExtractor):
    """Extract text from PDFs, with per-page OCR fallback for scanned pages.

    Uses pdfplumber for native text extraction. Pages with fewer than
    ``min_text_density`` characters are treated as scanned and OCR'd via
    pytesseract (if available).
    """

    def __init__(
        self,
        *,
        ocr_enabled: bool = True,
        min_text_density: int = _MIN_TEXT_DENSITY,
        ocr_resolution: int = 300,
    ) -> None:
        self._ocr_enabled = ocr_enabled
        self._min_text_density = min_text_density
        self._ocr_resolution = ocr_resolution

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in ("pdf",) or mime_type == "application/pdf"

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf"}

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        pages_text: list[str] = []
        warnings: list[str] = []
        ocr_confidences: list[float] = []
        ocr_used = False

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()

                if len(text) >= self._min_text_density:
                    # Native text extraction succeeded
                    pages_text.append(text)
                elif self._ocr_enabled:
                    # Scanned page — attempt OCR
                    ocr_text, confidence = self._ocr_page(page, i, filename)
                    if ocr_text:
                        pages_text.append(ocr_text)
                        ocr_confidences.append(confidence)
                        ocr_used = True
                        if confidence < 0.85:
                            warnings.append(
                                f"Page {i}: low OCR confidence ({confidence:.0%})"
                            )
                    else:
                        pages_text.append("")
                        warnings.append(f"Page {i}: OCR failed or unavailable")
                else:
                    # OCR disabled — keep whatever we got
                    pages_text.append(text)
                    if not text:
                        warnings.append(
                            f"Page {i}: no text extracted (scanned page? enable OCR)"
                        )

        full_text = "\n\n".join(pages_text)
        avg_confidence = (
            sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else None
        )

        metadata: dict = {"extractor": "pdf"}
        if ocr_used:
            metadata["ocr_used"] = True
            metadata["ocr_page_count"] = len(ocr_confidences)

        return ExtractionResult(
            text=full_text,
            page_count=page_count,
            ocr_confidence=avg_confidence,
            metadata=metadata,
            warnings=warnings,
        )

    def _ocr_page(
        self, page: object, page_num: int, filename: str
    ) -> tuple[str, float]:
        """OCR a single page. Returns (text, confidence) or ("", 0.0) on failure."""
        if _pytesseract is None:
            logger.warning(
                "pytesseract not installed — cannot OCR page %d of %s. "
                "Install with: pip install 'employee-help[casefile]'",
                page_num,
                filename,
            )
            return ("", 0.0)

        try:
            # Render page to PIL Image via pdfplumber (uses pypdfium2)
            pil_image = page.to_image(resolution=self._ocr_resolution).original  # type: ignore[union-attr]

            # Run OCR with word-level confidence data
            data = _pytesseract.image_to_data(
                pil_image, output_type=_pytesseract.Output.DICT
            )

            # Extract words and calculate average confidence
            words: list[str] = []
            confidences: list[int] = []
            for j, conf in enumerate(data["conf"]):
                conf_int = int(conf)
                if conf_int > 0:  # -1 = block/paragraph separator
                    word = data["text"][j].strip()
                    if word:
                        words.append(word)
                        confidences.append(conf_int)

            text = " ".join(words)
            avg_conf = (
                sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            )

            return (text, avg_conf)
        except Exception as exc:
            logger.warning(
                "OCR failed for page %d of %s: %s",
                page_num,
                filename,
                exc,
            )
            return ("", 0.0)
