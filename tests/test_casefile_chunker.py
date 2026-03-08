"""Tests for LITIGAGENT case file chunker (page-aware chunking)."""

from __future__ import annotations

import pytest

from employee_help.casefile.chunker import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    PAGE_SEPARATOR,
    _chunk_email,
    _chunk_generic,
    _chunk_pdf,
    _chunk_spreadsheet,
    _pdf_heading,
    _reindex,
    chunk_case_file,
)
from employee_help.processing.chunker import ChunkResult, content_hash, estimate_tokens
from employee_help.storage.models import FileType


# ── Helpers ─────────────────────────────────────────────────────


def _make_text(tokens: int) -> str:
    """Generate text of approximately the given token count (4 chars/token)."""
    word = "word "
    # estimate_tokens uses len(text) // 4, so we need ~tokens * 4 chars
    return (word * (tokens * 4 // len(word) + 1))[: tokens * 4]


def _make_pdf_text(pages: list[str]) -> str:
    """Join page texts with form-feed separator."""
    return PAGE_SEPARATOR.join(pages)


# ── chunk_case_file dispatch ────────────────────────────────────


class TestChunkCaseFileDispatch:
    def test_empty_text_returns_empty(self):
        assert chunk_case_file("", "test.pdf", FileType.PDF) == []
        assert chunk_case_file("   \n  ", "test.txt", FileType.TXT) == []

    def test_pdf_with_form_feed_uses_pdf_strategy(self):
        text = f"Page 1 content here.{PAGE_SEPARATOR}Page 2 content here."
        chunks = chunk_case_file(text, "report.pdf", FileType.PDF)
        assert len(chunks) >= 1
        assert "report.pdf" in chunks[0].heading_path

    def test_pdf_without_form_feed_uses_generic(self):
        text = "Just some text without page markers."
        chunks = chunk_case_file(text, "report.pdf", FileType.PDF)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "report.pdf"

    def test_eml_uses_email_strategy(self):
        text = "Subject: Test\nFrom: a@b.com\n\nBody text."
        chunks = chunk_case_file(text, "email.eml", FileType.EML)
        assert len(chunks) >= 1

    def test_msg_uses_email_strategy(self):
        text = "Subject: Test\nFrom: a@b.com\n\nBody text."
        chunks = chunk_case_file(text, "email.msg", FileType.MSG)
        assert len(chunks) >= 1

    def test_xlsx_uses_spreadsheet_strategy(self):
        text = "## Sheet1\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        chunks = chunk_case_file(text, "data.xlsx", FileType.XLSX)
        assert len(chunks) >= 1
        assert "Sheet1" in chunks[0].heading_path

    def test_csv_uses_spreadsheet_for_headings(self):
        text = "## Results\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        chunks = chunk_case_file(text, "data.csv", FileType.CSV)
        assert "Results" in chunks[0].heading_path

    def test_csv_without_headings_uses_generic(self):
        text = "a,b,c\n1,2,3"
        chunks = chunk_case_file(text, "data.csv", FileType.CSV)
        assert chunks[0].heading_path == "data.csv"

    def test_txt_uses_generic(self):
        text = "Some plain text content."
        chunks = chunk_case_file(text, "notes.txt", FileType.TXT)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "notes.txt"

    def test_docx_uses_generic(self):
        text = "Document content here."
        chunks = chunk_case_file(text, "letter.docx", FileType.DOCX)
        assert chunks[0].heading_path == "letter.docx"

    def test_image_uses_generic(self):
        text = "OCR extracted text from image."
        chunks = chunk_case_file(text, "scan.png", FileType.IMAGE)
        assert chunks[0].heading_path == "scan.png"


# ── Default parameters ──────────────────────────────────────────


class TestDefaults:
    def test_default_max_tokens_is_1000(self):
        assert DEFAULT_MAX_TOKENS == 1000

    def test_default_overlap_tokens_is_100(self):
        assert DEFAULT_OVERLAP_TOKENS == 100


# ── PDF chunking ────────────────────────────────────────────────


class TestChunkPdf:
    def test_single_page_single_chunk(self):
        text = _make_pdf_text(["Short page content."])
        chunks = _chunk_pdf(text, "doc.pdf", 1000, 100)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "doc.pdf > Page 1"
        assert chunks[0].chunk_index == 0

    def test_multi_page_each_fits(self):
        pages = ["Page one text.", "Page two text.", "Page three text."]
        text = _make_pdf_text(pages)
        chunks = _chunk_pdf(text, "doc.pdf", 1000, 100)
        # All 3 pages should merge into a single chunk (they're small)
        assert len(chunks) == 1
        for page in pages:
            assert page in chunks[0].content

    def test_multi_page_separate_when_large(self):
        page1 = _make_text(600)
        page2 = _make_text(600)
        text = _make_pdf_text([page1, page2])
        chunks = _chunk_pdf(text, "report.pdf", 1000, 100)
        # Each page ~600 tokens, can't merge (1200 > 1000), so 2 chunks
        assert len(chunks) == 2
        assert chunks[0].heading_path == "report.pdf > Page 1"
        assert chunks[1].heading_path == "report.pdf > Page 2"

    def test_oversized_page_sub_chunked(self):
        big_page = _make_text(2500)
        text = _make_pdf_text([big_page])
        chunks = _chunk_pdf(text, "big.pdf", 1000, 100)
        assert len(chunks) >= 3
        for c in chunks:
            assert c.token_count <= 1000 + 50  # Allow small estimation variance

    def test_empty_pages_skipped(self):
        text = _make_pdf_text(["Content here.", "", "  ", "More content."])
        chunks = _chunk_pdf(text, "sparse.pdf", 1000, 100)
        assert all(c.content.strip() for c in chunks)

    def test_page_heading_shows_page_range_when_merged(self):
        # 3 small pages that fit in one chunk
        pages = ["Short A.", "Short B.", "Short C."]
        text = _make_pdf_text(pages)
        chunks = _chunk_pdf(text, "doc.pdf", 1000, 100)
        assert len(chunks) == 1
        assert "Pages 1-3" in chunks[0].heading_path

    def test_chunk_index_sequential(self):
        pages = [_make_text(800) for _ in range(5)]
        text = _make_pdf_text(pages)
        chunks = _chunk_pdf(text, "multi.pdf", 1000, 100)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_content_hash_deterministic(self):
        text = _make_pdf_text(["Consistent content."])
        c1 = _chunk_pdf(text, "a.pdf", 1000, 100)
        c2 = _chunk_pdf(text, "a.pdf", 1000, 100)
        assert c1[0].content_hash == c2[0].content_hash

    def test_content_hash_is_sha256(self):
        text = _make_pdf_text(["Test content."])
        chunks = _chunk_pdf(text, "a.pdf", 1000, 100)
        assert chunks[0].content_hash == content_hash(chunks[0].content)

    def test_token_count_matches_content(self):
        text = _make_pdf_text(["Some text for token counting."])
        chunks = _chunk_pdf(text, "a.pdf", 1000, 100)
        for c in chunks:
            assert c.token_count == estimate_tokens(c.content)

    def test_mixed_small_and_large_pages(self):
        pages = [
            "Short.",
            _make_text(1200),  # Oversized
            "Also short.",
        ]
        text = _make_pdf_text(pages)
        chunks = _chunk_pdf(text, "mixed.pdf", 1000, 100)
        assert len(chunks) >= 2
        # The oversized page should be sub-chunked
        assert any("Page 2" in c.heading_path for c in chunks)

    def test_all_content_preserved(self):
        pages = ["Alpha bravo.", "Charlie delta.", "Echo foxtrot."]
        text = _make_pdf_text(pages)
        chunks = _chunk_pdf(text, "doc.pdf", 1000, 100)
        combined = " ".join(c.content for c in chunks)
        for page in pages:
            assert page in combined


# ── PDF heading helper ──────────────────────────────────────────


class TestPdfHeading:
    def test_single_page(self):
        assert _pdf_heading("report.pdf", 3, 3) == "report.pdf > Page 3"

    def test_page_range(self):
        assert _pdf_heading("report.pdf", 1, 5) == "report.pdf > Pages 1-5"


# ── Email chunking ──────────────────────────────────────────────


class TestChunkEmail:
    def test_small_single_email(self):
        text = "Subject: Hello\nFrom: a@b.com\n\nHi there."
        chunks = _chunk_email(text, "email.eml", 1000, 100)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "email.eml"
        assert "Subject: Hello" in chunks[0].content

    def test_large_single_email_split_by_paragraphs(self):
        body = "\n\n".join([_make_text(400) for _ in range(5)])
        text = f"Subject: Long\nFrom: a@b.com\n\n{body}"
        chunks = _chunk_email(text, "long.eml", 1000, 100)
        assert len(chunks) > 1

    def test_mbox_splits_on_separator(self):
        msg1 = "Subject: First\nFrom: a@b.com\n\nBody one."
        msg2 = "Subject: Second\nFrom: c@d.com\n\nBody two."
        text = f"{msg1}\n\n---\n\n{msg2}"
        chunks = _chunk_email(text, "archive.mbox", 1000, 100)
        assert len(chunks) == 2
        assert chunks[0].heading_path == "archive.mbox > Message 1"
        assert chunks[1].heading_path == "archive.mbox > Message 2"
        assert "Body one" in chunks[0].content
        assert "Body two" in chunks[1].content

    def test_mbox_large_message_sub_chunked(self):
        msg1 = "Subject: Short\n\nBrief."
        msg2 = "Subject: Long\n\n" + "\n\n".join(_make_text(400) for _ in range(5))
        text = f"{msg1}\n\n---\n\n{msg2}"
        chunks = _chunk_email(text, "archive.mbox", 1000, 100)
        assert len(chunks) >= 3

    def test_mbox_empty_messages_skipped(self):
        text = "Msg one.\n\n---\n\n   \n\n---\n\nMsg three."
        chunks = _chunk_email(text, "archive.mbox", 1000, 100)
        assert len(chunks) == 2
        assert all(c.content.strip() for c in chunks)

    def test_chunk_index_sequential_mbox(self):
        msgs = [f"Subject: Msg {i}\n\nBody {i}." for i in range(4)]
        text = "\n\n---\n\n".join(msgs)
        chunks = _chunk_email(text, "archive.mbox", 1000, 100)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i


# ── Spreadsheet chunking ───────────────────────────────────────


class TestChunkSpreadsheet:
    def test_single_sheet_no_heading(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        chunks = _chunk_spreadsheet(text, "data.xlsx", 1000, 100)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "data.xlsx"

    def test_multi_sheet_splits_on_headings(self):
        text = "## Sales\n\n| Q | Rev |\n|---|---|\n| Q1 | 100 |\n\n## Expenses\n\n| Q | Cost |\n|---|---|\n| Q1 | 50 |"
        chunks = _chunk_spreadsheet(text, "finances.xlsx", 1000, 100)
        assert len(chunks) == 2
        assert chunks[0].heading_path == "finances.xlsx > Sales"
        assert chunks[1].heading_path == "finances.xlsx > Expenses"

    def test_large_sheet_sub_chunked(self):
        rows = "\n".join(f"| {i} | {'x' * 100} |" for i in range(200))
        text = f"## BigSheet\n\n| ID | Data |\n|---|---|\n{rows}"
        chunks = _chunk_spreadsheet(text, "big.xlsx", 1000, 100)
        assert len(chunks) > 1
        assert all("BigSheet" in c.heading_path for c in chunks)

    def test_preamble_before_first_heading(self):
        text = "Summary data below.\n\n## Sheet1\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        chunks = _chunk_spreadsheet(text, "data.xlsx", 1000, 100)
        assert any("Preamble" in c.heading_path for c in chunks)

    def test_chunk_index_sequential(self):
        text = "## A\n\nData A.\n\n## B\n\nData B.\n\n## C\n\nData C."
        chunks = _chunk_spreadsheet(text, "multi.xlsx", 1000, 100)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i


# ── Generic chunking ───────────────────────────────────────────


class TestChunkGeneric:
    def test_small_text_single_chunk(self):
        text = "Short document content."
        chunks = _chunk_generic(text, "notes.txt", 1000, 100)
        assert len(chunks) == 1
        assert chunks[0].heading_path == "notes.txt"
        assert chunks[0].chunk_index == 0

    def test_large_text_split_by_paragraphs(self):
        paragraphs = [_make_text(400) for _ in range(5)]
        text = "\n\n".join(paragraphs)
        chunks = _chunk_generic(text, "long.txt", 1000, 100)
        assert len(chunks) > 1
        for c in chunks:
            assert c.token_count <= 1000 + 50  # Small estimation variance

    def test_heading_path_is_filename(self):
        text = "Content."
        chunks = _chunk_generic(text, "my_document.docx", 1000, 100)
        assert chunks[0].heading_path == "my_document.docx"

    def test_content_hash_present(self):
        text = "Test content."
        chunks = _chunk_generic(text, "test.txt", 1000, 100)
        assert chunks[0].content_hash == content_hash("Test content.")

    def test_chunk_index_sequential_large(self):
        text = "\n\n".join(_make_text(400) for _ in range(8))
        chunks = _chunk_generic(text, "big.txt", 1000, 100)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i


# ── _reindex helper ─────────────────────────────────────────────


class TestReindex:
    def test_reindexes_sequentially(self):
        chunks = [
            ChunkResult("a", "h", 5, 1, "ha"),
            ChunkResult("b", "h", 10, 1, "hb"),
            ChunkResult("c", "h", 20, 1, "hc"),
        ]
        result = _reindex(chunks)
        assert [c.chunk_index for c in result] == [0, 1, 2]

    def test_preserves_content(self):
        chunks = [
            ChunkResult("text1", "path1", 99, 5, "hash1"),
            ChunkResult("text2", "path2", 88, 10, "hash2"),
        ]
        result = _reindex(chunks)
        assert result[0].content == "text1"
        assert result[1].heading_path == "path2"
        assert result[1].content_hash == "hash2"


# ── Integration: chunk_case_file end-to-end ─────────────────────


class TestEndToEnd:
    def test_pdf_small_document(self):
        text = _make_pdf_text(["Page 1 content.", "Page 2 content."])
        chunks = chunk_case_file(text, "brief.pdf", FileType.PDF)
        assert len(chunks) >= 1
        assert all(c.heading_path.startswith("brief.pdf") for c in chunks)
        assert all(c.chunk_index == i for i, c in enumerate(chunks))

    def test_pdf_large_multi_page(self):
        pages = [_make_text(800) for _ in range(10)]
        text = _make_pdf_text(pages)
        chunks = chunk_case_file(text, "deposition.pdf", FileType.PDF)
        assert len(chunks) >= 8  # ~800 tokens each, most won't merge
        combined = " ".join(c.content for c in chunks)
        for page in pages:
            # Verify no content lost (at least start of each page present)
            assert page[:50] in combined

    def test_email_mbox(self):
        msgs = [f"Subject: Email {i}\nFrom: user{i}@test.com\n\nBody {i}." for i in range(3)]
        text = "\n\n---\n\n".join(msgs)
        chunks = chunk_case_file(text, "thread.mbox", FileType.EML)
        assert len(chunks) == 3

    def test_xlsx_multi_sheet(self):
        text = "## Payroll\n\n| Name | Salary |\n|---|---|\n| Jane | 80000 |\n\n## Benefits\n\n| Name | Plan |\n|---|---|\n| Jane | Premium |"
        chunks = chunk_case_file(text, "payroll.xlsx", FileType.XLSX)
        assert len(chunks) == 2
        assert "Payroll" in chunks[0].heading_path
        assert "Benefits" in chunks[1].heading_path

    def test_docx_generic(self):
        text = "# Employment Agreement\n\nThis agreement...\n\nSection 1.\n\nSection 2."
        chunks = chunk_case_file(text, "agreement.docx", FileType.DOCX)
        assert len(chunks) >= 1
        assert chunks[0].heading_path == "agreement.docx"

    def test_custom_max_tokens(self):
        text = _make_text(500)
        chunks_small = chunk_case_file(text, "doc.txt", FileType.TXT, max_tokens=200)
        chunks_large = chunk_case_file(text, "doc.txt", FileType.TXT, max_tokens=2000)
        assert len(chunks_small) > len(chunks_large)

    def test_all_chunks_have_valid_fields(self):
        pages = [_make_text(300) for _ in range(5)]
        text = _make_pdf_text(pages)
        chunks = chunk_case_file(text, "case.pdf", FileType.PDF)
        for c in chunks:
            assert isinstance(c.content, str)
            assert len(c.content) > 0
            assert isinstance(c.heading_path, str)
            assert len(c.heading_path) > 0
            assert isinstance(c.chunk_index, int)
            assert c.chunk_index >= 0
            assert isinstance(c.token_count, int)
            assert c.token_count > 0
            assert isinstance(c.content_hash, str)
            assert len(c.content_hash) == 64  # SHA-256 hex
