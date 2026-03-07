"""DocxExtractor — text extraction from Word documents."""

from __future__ import annotations

import io

from docx import Document  # type: ignore[import-untyped]
from docx.table import Table  # type: ignore[import-untyped]

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

# Heading style prefixes in python-docx
_HEADING_STYLES = {"Heading", "heading"}


class DocxExtractor(FileExtractor):
    """Extract text from .docx files.

    Extracts paragraphs (preserving heading structure), tables (as markdown),
    and headers/footers.
    """

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in ("docx",) or mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @property
    def supported_extensions(self) -> set[str]:
        return {"docx"}

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        warnings: list[str] = []
        sections: list[str] = []

        try:
            doc = Document(io.BytesIO(file_bytes))
        except Exception as exc:
            return ExtractionResult(
                text="",
                metadata={"extractor": "docx"},
                warnings=[f"Failed to open document: {exc}"],
            )

        # --- Headers / footers ---
        hf_text = self._extract_headers_footers(doc)
        if hf_text:
            sections.append(hf_text)

        # --- Body: paragraphs and tables ---
        body_parts = self._extract_body(doc)
        sections.extend(body_parts)

        full_text = "\n\n".join(s for s in sections if s)

        if not full_text.strip():
            warnings.append("No text extracted from document")

        return ExtractionResult(
            text=full_text,
            metadata={"extractor": "docx"},
            warnings=warnings,
        )

    def _extract_headers_footers(self, doc: Document) -> str:
        """Extract unique header/footer text from all sections."""
        parts: list[str] = []
        seen: set[str] = set()

        for section in doc.sections:
            for hf in (section.header, section.footer):
                if hf is None or not hf.is_linked_to_previous:
                    pass  # process it
                text = "\n".join(p.text.strip() for p in hf.paragraphs if p.text.strip())
                if text and text not in seen:
                    seen.add(text)
                    parts.append(text)

        return "\n".join(parts)

    def _extract_body(self, doc: Document) -> list[str]:
        """Extract paragraphs and tables in document order."""
        parts: list[str] = []

        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                # Paragraph
                from docx.text.paragraph import Paragraph  # type: ignore[import-untyped]

                para = Paragraph(element, doc)
                text = para.text.strip()
                if not text:
                    continue

                # Preserve heading structure with markdown-style prefixes
                style_name = para.style.name if para.style else ""
                if style_name and any(style_name.startswith(h) for h in _HEADING_STYLES):
                    level = self._heading_level(style_name)
                    parts.append(f"{'#' * level} {text}")
                else:
                    parts.append(text)

            elif tag == "tbl":
                # Table
                table = Table(element, doc)
                md = self._table_to_markdown(table)
                if md:
                    parts.append(md)

        return parts

    def _heading_level(self, style_name: str) -> int:
        """Extract heading level from style name (e.g. 'Heading 2' -> 2)."""
        for part in style_name.split():
            if part.isdigit():
                return min(int(part), 6)
        return 1

    def _table_to_markdown(self, table: Table) -> str:
        """Convert a docx table to a markdown table string."""
        rows = table.rows
        if not rows:
            return ""

        md_rows: list[str] = []
        for i, row in enumerate(rows):
            cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
            md_rows.append("| " + " | ".join(cells) + " |")
            if i == 0:
                md_rows.append("| " + " | ".join("---" for _ in cells) + " |")

        return "\n".join(md_rows)
