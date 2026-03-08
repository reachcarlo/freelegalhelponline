"""CSVExtractor — text extraction from .csv and .tsv files as markdown tables."""

from __future__ import annotations

import csv
import io

from charset_normalizer import from_bytes

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

_SUPPORTED_EXTENSIONS = {"csv", "tsv"}

_SUPPORTED_MIMES = {
    "text/csv",
    "text/tab-separated-values",
    "application/csv",
}


def _cell_to_str(value: str) -> str:
    """Escape pipe characters and newlines for markdown table cells."""
    return value.replace("|", "\\|").replace("\n", " ")


def _rows_to_markdown(rows: list[list[str]]) -> str:
    """Convert a list of string rows to a markdown table."""
    if not rows:
        return ""

    # Trim trailing empty rows
    while rows and all(c.strip() == "" for c in rows[-1]):
        rows.pop()

    if not rows:
        return ""

    # Find max column count
    max_cols = max(len(r) for r in rows)
    if max_cols == 0:
        return ""

    # Pad shorter rows
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    # Escape cells
    rows = [[_cell_to_str(c) for c in r] for r in rows]

    lines: list[str] = []

    # Header row
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")

    # Data rows
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _decode_bytes(file_bytes: bytes) -> tuple[str, str]:
    """Decode file bytes to string with encoding detection.

    Returns (text, encoding).
    """
    # Try UTF-8 first (most common)
    try:
        return file_bytes.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    # Fall back to charset_normalizer
    result = from_bytes(file_bytes).best()
    if result is not None:
        return str(result), result.encoding

    # Last resort
    return file_bytes.decode("latin-1"), "latin-1"


class CSVExtractor(FileExtractor):
    """Extract text from CSV and TSV files as markdown tables.

    Uses the stdlib ``csv`` module with ``csv.Sniffer`` for automatic
    delimiter detection. Falls back to comma for CSV and tab for TSV.
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
                metadata={"extractor": "csv", "encoding": "utf-8"},
                warnings=["No text extracted from document"],
            )

        text_content, encoding = _decode_bytes(file_bytes)

        if not text_content.strip():
            return ExtractionResult(
                text="",
                metadata={"extractor": "csv", "encoding": encoding},
                warnings=["No text extracted from document"],
            )

        # Detect delimiter
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        delimiter: str | None = None

        try:
            sample = text_content[:8192]
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            delimiter = dialect.delimiter
        except csv.Error:
            # Sniffer failed — fall back based on extension
            delimiter = "\t" if ext == "tsv" else ","

        try:
            reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
            rows = list(reader)
        except csv.Error as exc:
            return ExtractionResult(
                text=text_content,  # return raw text as fallback
                metadata={"extractor": "csv", "encoding": encoding},
                warnings=[f"CSV parsing failed, returning raw text: {exc}"],
            )

        md_table = _rows_to_markdown(rows)

        if not md_table:
            warnings.append("No text extracted from document")

        row_count = len(rows) - 1 if len(rows) > 1 else 0  # exclude header

        return ExtractionResult(
            text=md_table,
            metadata={
                "extractor": "csv",
                "encoding": encoding,
                "delimiter": repr(delimiter),
                "row_count": row_count,
                "column_count": max((len(r) for r in rows), default=0),
            },
            warnings=warnings,
        )
