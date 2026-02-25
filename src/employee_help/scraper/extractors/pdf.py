"""PDF content extraction for CRD documents.

Downloads and extracts text from PDF documents (fact sheets, brochures,
posters) while preserving structural information.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pdfplumber


@dataclass
class PdfExtractionResult:
    title: str
    markdown: str
    headings: list[str]
    source_url: str
    page_count: int
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


def extract_pdf(
    pdf_bytes: bytes,
    source_url: str,
) -> PdfExtractionResult:
    """Extract structured content from a PDF document.

    Args:
        pdf_bytes: Raw PDF file bytes.
        source_url: The URL this PDF was downloaded from.

    Returns:
        PdfExtractionResult with extracted Markdown and metadata.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        return _extract_from_file(tmp_path, source_url)
    finally:
        tmp_path.unlink(missing_ok=True)


def _extract_from_file(pdf_path: Path, source_url: str) -> PdfExtractionResult:
    """Extract content from a PDF file on disk."""
    pages_text: list[str] = []
    all_headings: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text)

            # Extract tables separately for better formatting
            tables = page.extract_tables()
            for table in tables:
                table_md = _table_to_markdown(table)
                if table_md:
                    pages_text.append(table_md)

    full_text = "\n\n".join(pages_text)

    # Detect title from first meaningful line
    title = _detect_title(full_text, source_url)

    # Detect headings (lines that appear to be section headers)
    all_headings = _detect_headings(full_text)

    # Convert to cleaner Markdown
    markdown = _text_to_markdown(full_text, all_headings)

    return PdfExtractionResult(
        title=title,
        markdown=markdown,
        headings=all_headings,
        source_url=source_url,
        page_count=page_count,
    )


def _detect_title(text: str, source_url: str) -> str:
    """Attempt to detect the document title from the extracted text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Strategy 1: Look for common CRD title patterns
    # CRD fact sheets often have a prominent title in the first few lines
    for line in lines[:10]:
        # Skip very short lines (page numbers, headers)
        if len(line) < 10:
            continue
        # Skip lines that look like boilerplate
        if any(
            kw in line.lower()
            for kw in ["california law", "civil rights department", "fact sheet", "www.", "http"]
        ):
            continue
        # The first substantial line that isn't boilerplate is likely the title
        if len(line) > 10:
            return line[:120]

    # Strategy 2: Derive from URL
    filename = source_url.rsplit("/", 1)[-1]
    name = filename.replace(".pdf", "").replace("-", " ").replace("_", " ")
    return name.strip().title()[:120]


def _detect_headings(text: str) -> list[str]:
    """Detect lines that appear to be section headings."""
    headings: list[str] = []
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue

        # Heuristics for heading detection in PDFs:
        # 1. All caps lines that aren't too long (likely section headers)
        if stripped.isupper() and 3 < len(stripped) < 100:
            headings.append(stripped)
            continue

        # 2. Lines ending with colon that are short (subsection headers)
        if stripped.endswith(":") and len(stripped) < 80 and not stripped.startswith("•"):
            headings.append(stripped.rstrip(":"))
            continue

    return headings


def _text_to_markdown(text: str, headings: list[str]) -> str:
    """Convert extracted PDF text to cleaner Markdown format."""
    lines = text.split("\n")
    md_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            md_lines.append("")
            continue

        # Convert detected headings to Markdown heading format
        if stripped in headings or stripped.rstrip(":") in headings:
            md_lines.append("")
            md_lines.append(f"## {stripped}")
            md_lines.append("")
            continue

        # Convert bullet points
        if stripped.startswith("•") or stripped.startswith("·"):
            md_lines.append(f"- {stripped[1:].strip()}")
            continue

        # Convert numbered items
        match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if match:
            md_lines.append(f"{match.group(1)}. {match.group(2)}")
            continue

        md_lines.append(stripped)

    result = "\n".join(md_lines)
    # Collapse excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table to Markdown."""
    if not table or not any(table):
        return ""

    # Clean cells
    clean_rows = []
    for row in table:
        clean_row = [(cell or "").strip() for cell in row]
        if any(clean_row):
            clean_rows.append(clean_row)

    if not clean_rows:
        return ""

    # Pad rows to same length
    max_cols = max(len(r) for r in clean_rows)
    for r in clean_rows:
        while len(r) < max_cols:
            r.append("")

    lines = []
    # Header
    lines.append("| " + " | ".join(clean_rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in clean_rows[0]) + " |")
    # Body
    for row in clean_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)
