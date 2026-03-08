"""ImageExtractor — OCR-based text extraction from image files."""

from __future__ import annotations

import io
import logging

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

logger = logging.getLogger(__name__)

try:
    import pytesseract as _pytesseract  # type: ignore[import-untyped]
except ImportError:
    _pytesseract = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment,misc]

_SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp"}

_SUPPORTED_MIMES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/x-bmp",
    "image/x-ms-bmp",
}


def _preprocess(img):  # type: ignore[no-untyped-def]
    """Apply preprocessing for OCR: EXIF orient, grayscale, denoise, contrast."""
    # Auto-orient based on EXIF data (common in phone photos)
    img = ImageOps.exif_transpose(img) or img

    # Convert to grayscale
    if img.mode != "L":
        img = img.convert("L")

    # Denoise with median filter (removes salt-and-pepper noise)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # Enhance contrast for better OCR
    img = ImageEnhance.Contrast(img).enhance(1.5)

    return img


def _deskew(img):  # type: ignore[no-untyped-def]
    """Attempt to detect and correct rotation using Tesseract OSD.

    Returns (corrected_image, angle_degrees). Falls back to (original, 0.0)
    on failure.
    """
    if _pytesseract is None:
        return img, 0.0

    try:
        osd = _pytesseract.image_to_osd(img, output_type=_pytesseract.Output.DICT)
        angle = int(osd.get("rotate", 0))
        if angle:
            img = img.rotate(angle, expand=True, fillcolor=255)
            return img, float(angle)
    except Exception:
        pass  # OSD can fail on small or low-contrast images

    return img, 0.0


def _ocr_image(img):  # type: ignore[no-untyped-def]
    """Run OCR on a PIL Image. Returns (text, confidence 0.0-1.0)."""
    data = _pytesseract.image_to_data(
        img, output_type=_pytesseract.Output.DICT
    )

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
    avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

    return text, avg_conf


def _extract_frames(img) -> list:  # type: ignore[type-arg]
    """Extract all frames from an image (handles multi-frame TIFF)."""
    frames = []
    try:
        while True:
            frames.append(img.copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    return frames if frames else [img]


class ImageExtractor(FileExtractor):
    """Extract text from images via OCR with confidence reporting.

    Supports PNG, JPEG, TIFF, and BMP formats. Applies preprocessing
    (grayscale conversion, denoising, contrast enhancement) and optional
    deskew before OCR. Multi-frame TIFF images are handled frame-by-frame.

    Requires ``pytesseract`` and ``Pillow`` (part of the ``[casefile]``
    dependency group).
    """

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in _SUPPORTED_EXTENSIONS or mime_type in _SUPPORTED_MIMES

    @property
    def supported_extensions(self) -> set[str]:
        return set(_SUPPORTED_EXTENSIONS)

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        warnings: list[str] = []

        if _pytesseract is None:
            return ExtractionResult(
                text="",
                metadata={"extractor": "image"},
                warnings=["pytesseract is not installed; cannot OCR images"],
            )

        if not file_bytes:
            return ExtractionResult(
                text="",
                metadata={"extractor": "image"},
                warnings=["No text extracted from document"],
            )

        try:
            img = Image.open(io.BytesIO(file_bytes))
        except Exception as exc:
            return ExtractionResult(
                text="",
                metadata={"extractor": "image"},
                warnings=[f"Failed to open image: {exc}"],
            )

        # Handle multi-frame TIFF
        frames = _extract_frames(img)

        pages_text: list[str] = []
        ocr_confidences: list[float] = []
        preprocessing = ["grayscale", "denoise", "contrast"]
        deskewed = False

        for i, frame in enumerate(frames, start=1):
            try:
                processed = _preprocess(frame)
                processed, skew_angle = _deskew(processed)
                if skew_angle != 0.0:
                    deskewed = True

                text, confidence = _ocr_image(processed)

                if text:
                    pages_text.append(text)
                    ocr_confidences.append(confidence)
                    if confidence < 0.85:
                        label = f"Page {i}: " if len(frames) > 1 else ""
                        warnings.append(
                            f"{label}low OCR confidence ({confidence:.0%})"
                        )
                else:
                    pages_text.append("")
                    label = f"Page {i}: " if len(frames) > 1 else ""
                    warnings.append(f"{label}OCR produced no text")

            except Exception as exc:
                logger.warning(
                    "OCR failed for frame %d of %s: %s", i, filename, exc
                )
                pages_text.append("")
                label = f"Page {i}: " if len(frames) > 1 else ""
                warnings.append(f"{label}OCR failed: {exc}")

        full_text = "\n\n".join(pages_text)
        avg_confidence = (
            sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else None
        )

        if deskewed:
            preprocessing.append("deskew")

        metadata: dict = {
            "extractor": "image",
            "ocr_used": True,
            "preprocessing": preprocessing,
        }

        if len(frames) > 1:
            metadata["frame_count"] = len(frames)

        if not full_text.strip():
            if not any("No text extracted" in w for w in warnings):
                warnings.append("No text extracted from document")

        return ExtractionResult(
            text=full_text,
            page_count=len(frames) if len(frames) > 1 else 1,
            ocr_confidence=avg_confidence,
            metadata=metadata,
            warnings=warnings,
        )
