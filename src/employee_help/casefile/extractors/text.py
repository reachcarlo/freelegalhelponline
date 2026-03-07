"""PlainTextExtractor — text extraction from plain text files."""

from __future__ import annotations

from charset_normalizer import from_bytes

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

_SUPPORTED_EXTENSIONS = {"txt", "md", "rtf"}

_SUPPORTED_MIMES = {
    "text/plain",
    "text/markdown",
    "text/rtf",
    "application/rtf",
}


class PlainTextExtractor(FileExtractor):
    """Extract text from plain text files (.txt, .md, .rtf).

    Uses charset_normalizer for encoding detection with UTF-8 preference.
    """

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in _SUPPORTED_EXTENSIONS or mime_type in _SUPPORTED_MIMES

    @property
    def supported_extensions(self) -> set[str]:
        return set(_SUPPORTED_EXTENSIONS)

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        warnings: list[str] = []

        if not file_bytes:
            return ExtractionResult(
                text="",
                metadata={"extractor": "text", "encoding": "utf-8"},
                warnings=["No text extracted from document"],
            )

        # Try UTF-8 first (most common)
        try:
            text = file_bytes.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            # Fall back to charset_normalizer detection
            result = from_bytes(file_bytes).best()
            if result is not None:
                text = str(result)
                encoding = result.encoding
            else:
                # Last resort: latin-1 (never fails)
                text = file_bytes.decode("latin-1")
                encoding = "latin-1"
                warnings.append(
                    "Could not detect encoding; fell back to latin-1"
                )

        if not text.strip():
            warnings.append("No text extracted from document")

        return ExtractionResult(
            text=text,
            metadata={"extractor": "text", "encoding": encoding},
            warnings=warnings,
        )
