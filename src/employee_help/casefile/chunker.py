"""Page-aware chunking for LITIGAGENT case files.

Splits case file text into chunks optimized for retrieval, with strategies
that vary by file type:
- PDFs: page-boundary chunking (form-feed markers from PDFExtractor)
- Emails: message-boundary chunking (header pattern / mbox separator)
- Spreadsheets: sheet-header chunking (## headings from ExcelExtractor)
- All others: paragraph-based chunking
"""

from __future__ import annotations

import re

from employee_help.processing.chunker import (
    ChunkResult,
    _split_large_section,
    content_hash,
    estimate_tokens,
)
from employee_help.storage.models import FileType

# Form-feed character used by PDFExtractor as page separator.
PAGE_SEPARATOR = "\f"

# Default chunk sizes for case files (smaller than KB for precision).
DEFAULT_MAX_TOKENS = 1000
DEFAULT_OVERLAP_TOKENS = 100

# Mbox message separator used by EmailExtractor.
_MBOX_SEPARATOR = "\n\n---\n\n"

# Email header pattern to detect message boundaries in single emails.
_EMAIL_HEADER_RE = re.compile(
    r"^(Subject|From|To|Date|Cc):\s",
    re.MULTILINE,
)

# Sheet heading pattern from ExcelExtractor (multi-sheet XLSX).
_SHEET_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def chunk_case_file(
    edited_text: str,
    filename: str,
    file_type: FileType,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[ChunkResult]:
    """Chunk case file text for RAG retrieval.

    Strategy varies by file type:
    - PDFs: Page-aware chunking (split on form-feed page markers)
    - Emails: Message-boundary chunking (mbox separator or header blocks)
    - Spreadsheets: Sheet-header chunking (## headings from extractors)
    - All others: Paragraph-based chunking

    Args:
        edited_text: The (potentially user-edited) extracted text.
        filename: Original filename (used in heading_path).
        file_type: FileType enum for strategy selection.
        max_tokens: Maximum tokens per chunk (default 1000).
        overlap_tokens: Overlap tokens between consecutive chunks.

    Returns:
        List of ChunkResult objects.
    """
    if not edited_text.strip():
        return []

    if file_type == FileType.PDF and PAGE_SEPARATOR in edited_text:
        return _chunk_pdf(edited_text, filename, max_tokens, overlap_tokens)
    elif file_type in (FileType.EML, FileType.MSG):
        return _chunk_email(edited_text, filename, max_tokens, overlap_tokens)
    elif file_type in (FileType.XLSX, FileType.CSV):
        return _chunk_spreadsheet(edited_text, filename, max_tokens, overlap_tokens)
    else:
        return _chunk_generic(edited_text, filename, max_tokens, overlap_tokens)


def _chunk_pdf(
    text: str,
    filename: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Chunk PDF text at page boundaries (form-feed markers).

    Each page becomes one or more chunks. Pages within max_tokens are kept
    whole. Oversized pages are sub-chunked by paragraph boundaries.
    """
    pages = text.split(PAGE_SEPARATOR)
    chunks: list[ChunkResult] = []

    # Accumulator for merging small consecutive pages.
    acc_text = ""
    acc_start_page = 1

    for i, page_text in enumerate(pages):
        page_num = i + 1
        page_text = page_text.strip()
        if not page_text:
            continue

        page_tokens = estimate_tokens(page_text)

        # If a single page exceeds max_tokens, flush accumulator first,
        # then sub-chunk the page.
        if page_tokens > max_tokens:
            # Flush accumulator
            if acc_text:
                heading = _pdf_heading(filename, acc_start_page, page_num - 1)
                _flush_section(acc_text, heading, chunks, max_tokens, overlap_tokens)
                acc_text = ""

            # Sub-chunk the oversized page
            heading = _pdf_heading(filename, page_num, page_num)
            sub_chunks = _split_large_section(
                page_text, heading, len(chunks), max_tokens, overlap_tokens,
            )
            chunks.extend(sub_chunks)
            acc_start_page = page_num + 1
            continue

        # Try to accumulate this page with previous small pages.
        if acc_text:
            combined = acc_text + "\n\n" + page_text
            combined_tokens = estimate_tokens(combined)
            if combined_tokens <= max_tokens:
                acc_text = combined
                continue
            else:
                # Flush accumulator, start new accumulation with this page.
                heading = _pdf_heading(filename, acc_start_page, page_num - 1)
                _flush_section(acc_text, heading, chunks, max_tokens, overlap_tokens)
                acc_text = page_text
                acc_start_page = page_num
        else:
            acc_text = page_text
            acc_start_page = page_num

    # Flush remaining accumulator.
    if acc_text:
        # Determine the last page number from total pages.
        last_page = len(pages)
        heading = _pdf_heading(filename, acc_start_page, last_page)
        _flush_section(acc_text, heading, chunks, max_tokens, overlap_tokens)

    # Re-index chunks sequentially.
    return _reindex(chunks)


def _pdf_heading(filename: str, start_page: int, end_page: int) -> str:
    """Build heading path for PDF chunks."""
    if start_page == end_page:
        return f"{filename} > Page {start_page}"
    return f"{filename} > Pages {start_page}-{end_page}"


def _chunk_email(
    text: str,
    filename: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Chunk email text at message boundaries.

    For mbox archives: split on the '---' separator between messages.
    For single emails: chunk as a single section (or by paragraphs if large).
    """
    # Mbox archive — split on message separator.
    if _MBOX_SEPARATOR in text:
        messages = text.split(_MBOX_SEPARATOR)
        chunks: list[ChunkResult] = []

        for i, msg_text in enumerate(messages):
            msg_text = msg_text.strip()
            if not msg_text:
                continue

            msg_num = i + 1
            heading = f"{filename} > Message {msg_num}"
            msg_tokens = estimate_tokens(msg_text)

            if msg_tokens <= max_tokens:
                chunks.append(
                    ChunkResult(
                        content=msg_text,
                        heading_path=heading,
                        chunk_index=len(chunks),
                        token_count=msg_tokens,
                        content_hash=content_hash(msg_text),
                    )
                )
            else:
                sub_chunks = _split_large_section(
                    msg_text, heading, len(chunks), max_tokens, overlap_tokens,
                )
                chunks.extend(sub_chunks)

        return _reindex(chunks)

    # Single email — chunk as one section.
    heading = filename
    tokens = estimate_tokens(text)
    if tokens <= max_tokens:
        return [
            ChunkResult(
                content=text,
                heading_path=heading,
                chunk_index=0,
                token_count=tokens,
                content_hash=content_hash(text),
            )
        ]

    # Split by paragraphs for large single emails.
    sub_chunks = _split_large_section(
        text, heading, 0, max_tokens, overlap_tokens,
    )
    return _reindex(sub_chunks)


def _chunk_spreadsheet(
    text: str,
    filename: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Chunk spreadsheet text at sheet boundaries (## headings).

    Multi-sheet XLSX files have ## SheetName headers from ExcelExtractor.
    Single-sheet files and CSVs are chunked generically.
    """
    # Find sheet sections via ## headings.
    matches = list(_SHEET_HEADING_RE.finditer(text))

    if not matches:
        # Single-sheet or CSV — chunk generically.
        return _chunk_generic(text, filename, max_tokens, overlap_tokens)

    chunks: list[ChunkResult] = []
    sections: list[tuple[str, str]] = []  # (sheet_name, section_text)

    for j, m in enumerate(matches):
        sheet_name = m.group(1)
        start = m.start()
        end = matches[j + 1].start() if j + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        sections.append((sheet_name, section_text))

    # Include any text before the first heading.
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.insert(0, ("Preamble", preamble))

    for sheet_name, section_text in sections:
        if not section_text:
            continue

        heading = f"{filename} > {sheet_name}"
        sec_tokens = estimate_tokens(section_text)

        if sec_tokens <= max_tokens:
            chunks.append(
                ChunkResult(
                    content=section_text,
                    heading_path=heading,
                    chunk_index=len(chunks),
                    token_count=sec_tokens,
                    content_hash=content_hash(section_text),
                )
            )
        else:
            sub_chunks = _split_large_section(
                section_text, heading, len(chunks), max_tokens, overlap_tokens,
            )
            chunks.extend(sub_chunks)

    return _reindex(chunks)


def _chunk_generic(
    text: str,
    filename: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Generic paragraph-based chunking for text files, DOCX, images, etc."""
    heading = filename
    tokens = estimate_tokens(text)

    if tokens <= max_tokens:
        return [
            ChunkResult(
                content=text,
                heading_path=heading,
                chunk_index=0,
                token_count=tokens,
                content_hash=content_hash(text),
            )
        ]

    sub_chunks = _split_large_section(
        text, heading, 0, max_tokens, overlap_tokens,
    )
    return _reindex(sub_chunks)


def _flush_section(
    text: str,
    heading: str,
    chunks: list[ChunkResult],
    max_tokens: int,
    overlap_tokens: int,
) -> None:
    """Flush accumulated text as one or more chunks (mutates chunks list)."""
    text = text.strip()
    if not text:
        return

    tokens = estimate_tokens(text)
    if tokens <= max_tokens:
        chunks.append(
            ChunkResult(
                content=text,
                heading_path=heading,
                chunk_index=len(chunks),
                token_count=tokens,
                content_hash=content_hash(text),
            )
        )
    else:
        sub_chunks = _split_large_section(
            text, heading, len(chunks), max_tokens, overlap_tokens,
        )
        chunks.extend(sub_chunks)


def _reindex(chunks: list[ChunkResult]) -> list[ChunkResult]:
    """Re-index chunks sequentially starting from 0."""
    return [
        ChunkResult(
            content=c.content,
            heading_path=c.heading_path,
            chunk_index=i,
            token_count=c.token_count,
            content_hash=c.content_hash,
        )
        for i, c in enumerate(chunks)
    ]
