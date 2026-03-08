"""Tests for LITIGAGENT ImageExtractor (L2.7)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.image import ImageExtractor


# --- Helpers ---


def _mock_ocr_data(words_and_confs: list[tuple[str, int]]) -> dict:
    """Build pytesseract image_to_data return value."""
    return {
        "text": [w for w, _ in words_and_confs],
        "conf": [c for _, c in words_and_confs],
    }


def _mock_image(mode: str = "RGB", size: tuple = (100, 100)):
    """Create a mock PIL Image."""
    img = MagicMock()
    img.mode = mode
    img.size = size
    img.copy.return_value = img
    img.convert.return_value = img
    img.filter.return_value = img
    img.rotate.return_value = img
    img.seek.side_effect = EOFError  # Single frame by default
    img.tell.return_value = 0
    return img


def _mock_multi_frame(count: int):
    """Create a mock PIL Image with multiple frames (for TIFF)."""
    img = MagicMock()
    img.mode = "RGB"
    img.size = (100, 100)
    img.convert.return_value = img
    img.filter.return_value = img
    img.rotate.return_value = img

    # Track frame position
    frame_pos = [0]
    frames = [MagicMock() for _ in range(count)]
    for f in frames:
        f.mode = "RGB"
        f.size = (100, 100)
        f.convert.return_value = f
        f.filter.return_value = f
        f.rotate.return_value = f

    def copy():
        return frames[frame_pos[0]]

    def seek(n):
        if n >= count:
            raise EOFError
        frame_pos[0] = n

    def tell():
        return frame_pos[0]

    img.copy.side_effect = copy
    img.seek.side_effect = seek
    img.tell.side_effect = tell

    return img, frames


# --- Interface tests ---


class TestImageExtractorInterface:
    def test_can_extract_png(self):
        assert ImageExtractor().can_extract("image/png", "png") is True

    def test_can_extract_jpg(self):
        assert ImageExtractor().can_extract("image/jpeg", "jpg") is True

    def test_can_extract_jpeg(self):
        assert ImageExtractor().can_extract("image/jpeg", "jpeg") is True

    def test_can_extract_tiff(self):
        assert ImageExtractor().can_extract("image/tiff", "tiff") is True

    def test_can_extract_tif(self):
        assert ImageExtractor().can_extract("image/tiff", "tif") is True

    def test_can_extract_bmp(self):
        assert ImageExtractor().can_extract("image/bmp", "bmp") is True

    def test_can_extract_by_mime_only(self):
        assert ImageExtractor().can_extract("image/png", "unknown") is True

    def test_can_extract_by_extension_only(self):
        assert ImageExtractor().can_extract("application/octet-stream", "png") is True

    def test_can_extract_x_bmp_mime(self):
        assert ImageExtractor().can_extract("image/x-bmp", "unknown") is True

    def test_cannot_extract_pdf(self):
        assert ImageExtractor().can_extract("application/pdf", "pdf") is False

    def test_cannot_extract_docx(self):
        assert ImageExtractor().can_extract("application/msword", "docx") is False

    def test_supported_extensions(self):
        assert ImageExtractor().supported_extensions == {
            "png", "jpg", "jpeg", "tiff", "tif", "bmp"
        }

    def test_isinstance_file_extractor(self):
        assert isinstance(ImageExtractor(), FileExtractor)


# --- OCR extraction ---


class TestImageOCRExtraction:
    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_simple_image_ocr(self, mock_deskew, mock_preprocess, mock_tess, mock_pil):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("Hello", 95), ("world", 90), ("", -1),
        ])

        result = ImageExtractor().extract(b"fake-image-data", "photo.png")

        assert isinstance(result, ExtractionResult)
        assert "Hello" in result.text
        assert "world" in result.text
        assert result.ocr_confidence is not None
        assert result.ocr_confidence > 0.85
        assert result.metadata["extractor"] == "image"
        assert result.metadata["ocr_used"] is True
        assert result.page_count == 1
        assert result.warnings == []

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_confidence_calculated_correctly(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("word1", 80), ("word2", 60), ("word3", 70),
        ])

        result = ImageExtractor().extract(b"fake", "test.jpg")

        expected = (80 + 60 + 70) / 3 / 100.0
        assert result.ocr_confidence == pytest.approx(expected)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_low_confidence_warning(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("blurry", 50), ("text", 40),
        ])

        result = ImageExtractor().extract(b"fake", "blurry.png")

        assert any("low OCR confidence" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_high_confidence_no_warning(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("clear", 95), ("text", 92),
        ])

        result = ImageExtractor().extract(b"fake", "clear.png")

        assert result.ocr_confidence is not None
        assert result.ocr_confidence > 0.85
        assert not any("low OCR confidence" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_separator_entries_excluded_from_confidence(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("", -1), ("word", 90), ("", -1), ("other", 80), ("", -1),
        ])

        result = ImageExtractor().extract(b"fake", "test.png")

        # Only 90 and 80 should count, not -1 separators
        expected = (90 + 80) / 2 / 100.0
        assert result.ocr_confidence == pytest.approx(expected)
        assert "word" in result.text
        assert "other" in result.text

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_metadata_fields(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("text", 90)])

        result = ImageExtractor().extract(b"fake", "test.png")

        assert result.metadata["extractor"] == "image"
        assert result.metadata["ocr_used"] is True
        assert "preprocessing" in result.metadata
        assert "grayscale" in result.metadata["preprocessing"]
        assert "denoise" in result.metadata["preprocessing"]
        assert "contrast" in result.metadata["preprocessing"]


# --- Preprocessing ---


class TestImagePreprocessing:
    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_preprocess_called(self, mock_deskew, mock_tess, mock_pil):
        """Verify preprocessing pipeline runs (grayscale, denoise, contrast)."""
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("text", 90)])

        result = ImageExtractor().extract(b"fake", "test.png")

        # _preprocess is called on the frame — verify convert was called
        assert result.metadata["preprocessing"] == ["grayscale", "denoise", "contrast"]


# --- Deskew ---


class TestImageDeskew:
    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_deskew_applied_metadata(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 90.0)  # Rotated 90 degrees

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("text", 90)])

        result = ImageExtractor().extract(b"fake", "rotated.jpg")

        assert "deskew" in result.metadata["preprocessing"]

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_no_deskew_not_in_metadata(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)  # No rotation

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("text", 90)])

        result = ImageExtractor().extract(b"fake", "straight.jpg")

        assert "deskew" not in result.metadata["preprocessing"]

    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_deskew_osd_failure_graceful(self, mock_tess):
        """OSD failure should return original image unchanged."""
        from employee_help.casefile.extractors.image import _deskew

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_osd.side_effect = RuntimeError("OSD failed")

        img = _mock_image()
        result_img, angle = _deskew(img)

        assert angle == 0.0

    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_deskew_rotates_when_angle_detected(self, mock_tess):
        from employee_help.casefile.extractors.image import _deskew

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_osd.return_value = {"rotate": 90}

        img = _mock_image()
        result_img, angle = _deskew(img)

        assert angle == 90.0
        img.rotate.assert_called_once_with(90, expand=True, fillcolor=255)

    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_deskew_zero_angle_no_rotate(self, mock_tess):
        from employee_help.casefile.extractors.image import _deskew

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_osd.return_value = {"rotate": 0}

        img = _mock_image()
        _, angle = _deskew(img)

        assert angle == 0.0
        img.rotate.assert_not_called()


# --- Multi-frame TIFF ---


class TestImageMultiFrame:
    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_multi_frame_tiff(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img, frames = _mock_multi_frame(3)
        mock_pil.open.return_value = img
        for f in frames:
            mock_preprocess.return_value = f
            mock_deskew.return_value = (f, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.side_effect = [
            _mock_ocr_data([("page1", 90)]),
            _mock_ocr_data([("page2", 85)]),
            _mock_ocr_data([("page3", 80)]),
        ]

        result = ImageExtractor().extract(b"fake", "multi.tiff")

        assert "page1" in result.text
        assert "page2" in result.text
        assert "page3" in result.text
        assert result.page_count == 3
        assert result.metadata["frame_count"] == 3
        expected_conf = (0.90 + 0.85 + 0.80) / 3
        assert result.ocr_confidence == pytest.approx(expected_conf)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_multi_frame_low_confidence_per_page(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img, frames = _mock_multi_frame(2)
        mock_pil.open.return_value = img
        for f in frames:
            mock_preprocess.return_value = f
            mock_deskew.return_value = (f, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.side_effect = [
            _mock_ocr_data([("clear", 95)]),
            _mock_ocr_data([("blurry", 50)]),
        ]

        result = ImageExtractor().extract(b"fake", "mixed.tiff")

        low_warnings = [w for w in result.warnings if "low OCR confidence" in w]
        assert len(low_warnings) == 1
        assert "Page 2" in low_warnings[0]

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_single_frame_no_frame_count(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("text", 90)])

        result = ImageExtractor().extract(b"fake", "single.png")

        assert "frame_count" not in result.metadata
        assert result.page_count == 1


# --- Graceful degradation ---


class TestImageGracefulDegradation:
    @patch("employee_help.casefile.extractors.image._pytesseract", None)
    def test_pytesseract_not_installed(self):
        result = ImageExtractor().extract(b"fake-data", "photo.png")

        assert result.text == ""
        assert any("pytesseract is not installed" in w for w in result.warnings)
        assert result.metadata["extractor"] == "image"

    def test_empty_bytes(self):
        result = ImageExtractor().extract(b"", "empty.png")

        assert result.text == ""
        assert any("No text extracted" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_invalid_image_data(self, mock_tess, mock_pil):
        mock_pil.open.side_effect = Exception("cannot identify image file")

        result = ImageExtractor().extract(b"not-an-image", "bad.png")

        assert result.text == ""
        assert any("Failed to open image" in w for w in result.warnings)

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_ocr_produces_no_text(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.return_value = img
        mock_deskew.return_value = (img, 0.0)

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([("", -1)])

        result = ImageExtractor().extract(b"fake", "blank.png")

        assert result.text == ""
        assert any("OCR produced no text" in w for w in result.warnings)
        assert any("No text extracted" in w for w in result.warnings)
        assert result.ocr_confidence is None

    @patch("employee_help.casefile.extractors.image.Image")
    @patch("employee_help.casefile.extractors.image._pytesseract")
    @patch("employee_help.casefile.extractors.image._preprocess")
    @patch("employee_help.casefile.extractors.image._deskew")
    def test_ocr_exception_handled(
        self, mock_deskew, mock_preprocess, mock_tess, mock_pil
    ):
        img = _mock_image()
        mock_pil.open.return_value = img
        mock_preprocess.side_effect = RuntimeError("processing failed")

        result = ImageExtractor().extract(b"fake", "broken.png")

        assert result.text == ""
        assert any("OCR failed" in w for w in result.warnings)


# --- Helper function unit tests ---


class TestOCRImageHelper:
    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_ocr_image_words_joined(self, mock_tess):
        from employee_help.casefile.extractors.image import _ocr_image

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("Hello", 90), ("world", 85),
        ])

        text, conf = _ocr_image(MagicMock())

        assert text == "Hello world"
        assert conf == pytest.approx(87.5 / 100.0)

    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_ocr_image_empty_words_skipped(self, mock_tess):
        from employee_help.casefile.extractors.image import _ocr_image

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("", -1), ("  ", 50), ("word", 90), ("", -1),
        ])

        text, conf = _ocr_image(MagicMock())

        assert text == "word"
        assert conf == pytest.approx(0.90)

    @patch("employee_help.casefile.extractors.image._pytesseract")
    def test_ocr_image_all_separators(self, mock_tess):
        from employee_help.casefile.extractors.image import _ocr_image

        mock_tess.Output.DICT = "dict"
        mock_tess.image_to_data.return_value = _mock_ocr_data([
            ("", -1), ("", -1),
        ])

        text, conf = _ocr_image(MagicMock())

        assert text == ""
        assert conf == 0.0


class TestExtractFramesHelper:
    def test_single_frame(self):
        from employee_help.casefile.extractors.image import _extract_frames

        img = _mock_image()
        frames = _extract_frames(img)

        assert len(frames) == 1

    def test_multi_frame(self):
        from employee_help.casefile.extractors.image import _extract_frames

        img, expected_frames = _mock_multi_frame(3)
        frames = _extract_frames(img)

        assert len(frames) == 3
