"""Tests for LITIGAGENT CSVExtractor (L2.6)."""

from __future__ import annotations

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.csv_ext import CSVExtractor


# --- Interface tests ---


class TestCSVExtractorInterface:
    def test_can_extract_csv_extension(self):
        assert CSVExtractor().can_extract("application/octet-stream", "csv") is True

    def test_can_extract_tsv_extension(self):
        assert CSVExtractor().can_extract("application/octet-stream", "tsv") is True

    def test_can_extract_by_mime_text_csv(self):
        assert CSVExtractor().can_extract("text/csv", "unknown") is True

    def test_can_extract_by_mime_tsv(self):
        assert CSVExtractor().can_extract("text/tab-separated-values", "unknown") is True

    def test_can_extract_by_mime_application_csv(self):
        assert CSVExtractor().can_extract("application/csv", "unknown") is True

    def test_cannot_extract_xlsx(self):
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert CSVExtractor().can_extract(mime, "xlsx") is False

    def test_cannot_extract_pdf(self):
        assert CSVExtractor().can_extract("application/pdf", "pdf") is False

    def test_supported_extensions(self):
        assert CSVExtractor().supported_extensions == {"csv", "tsv"}

    def test_isinstance_file_extractor(self):
        assert isinstance(CSVExtractor(), FileExtractor)


# --- CSV extraction ---


class TestCSVExtraction:
    def test_simple_csv(self):
        data = b"Name,Age\nAlice,30\nBob,25\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert isinstance(result, ExtractionResult)
        assert "| Name | Age |" in result.text
        assert "| --- | --- |" in result.text
        assert "| Alice | 30 |" in result.text
        assert "| Bob | 25 |" in result.text
        assert result.metadata["extractor"] == "csv"
        assert result.metadata["encoding"] == "utf-8"
        assert result.warnings == []

    def test_csv_with_quoted_fields(self):
        data = b'Name,Address\nAlice,"123 Main St, Apt 4"\nBob,"456 Oak Ave"\n'
        result = CSVExtractor().extract(data, "test.csv")

        assert "| Alice | 123 Main St, Apt 4 |" in result.text

    def test_csv_pipe_escaped(self):
        data = b"Col\na|b\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert "a\\|b" in result.text

    def test_csv_row_count_metadata(self):
        data = b"A,B\n1,2\n3,4\n5,6\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert result.metadata["row_count"] == 3
        assert result.metadata["column_count"] == 2

    def test_csv_single_column(self):
        data = b"Items\napple\nbanana\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert "| Items |" in result.text
        assert "| apple |" in result.text

    def test_csv_header_only(self):
        data = b"A,B,C\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert "| A | B | C |" in result.text
        assert result.metadata["row_count"] == 0


# --- TSV extraction ---


class TestTSVExtraction:
    def test_simple_tsv(self):
        data = b"Name\tAge\nAlice\t30\nBob\t25\n"
        result = CSVExtractor().extract(data, "data.tsv")

        assert "| Name | Age |" in result.text
        assert "| Alice | 30 |" in result.text

    def test_tsv_delimiter_detection(self):
        data = b"Col1\tCol2\n1\t2\n"
        result = CSVExtractor().extract(data, "data.tsv")

        assert result.metadata["delimiter"] == repr("\t")


# --- Delimiter detection ---


class TestCSVDelimiterDetection:
    def test_comma_detected(self):
        data = b"A,B,C\n1,2,3\n4,5,6\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert result.metadata["delimiter"] == repr(",")

    def test_semicolon_detected(self):
        data = b"A;B;C\n1;2;3\n4;5;6\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert "| A | B | C |" in result.text
        assert result.metadata["delimiter"] == repr(";")

    def test_tab_detected(self):
        data = b"A\tB\tC\n1\t2\t3\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert result.metadata["delimiter"] == repr("\t")


# --- Edge cases ---


class TestCSVEdgeCases:
    def test_empty_bytes(self):
        result = CSVExtractor().extract(b"", "empty.csv")

        assert result.text == ""
        assert "No text extracted" in result.warnings[0]

    def test_whitespace_only(self):
        result = CSVExtractor().extract(b"   \n  \n", "blank.csv")

        assert result.text == ""
        assert any("No text extracted" in w for w in result.warnings)

    def test_single_value(self):
        data = b"Value\nHello\n"
        result = CSVExtractor().extract(data, "single.csv")

        assert "| Value |" in result.text
        assert "| Hello |" in result.text

    def test_ragged_rows_padded(self):
        data = b"A,B,C\n1,2\n3,4,5\n"
        result = CSVExtractor().extract(data, "ragged.csv")

        # Row with 2 values should be padded to 3
        lines = result.text.split("\n")
        data_lines = [l for l in lines if l.startswith("|") and "---" not in l]
        for line in data_lines:
            # Each row should have 4 pipes (3 columns)
            assert line.count("|") == 4

    def test_trailing_empty_rows_trimmed(self):
        data = b"A\n1\n\n\n"
        result = CSVExtractor().extract(data, "test.csv")

        lines = [l for l in result.text.split("\n") if l.startswith("|")]
        # header + separator + 1 data row = 3
        assert len(lines) == 3

    def test_utf8_content(self):
        data = "Name,City\nJosé,São Paulo\n".encode("utf-8")
        result = CSVExtractor().extract(data, "test.csv")

        assert "José" in result.text
        assert "São Paulo" in result.text
        assert result.metadata["encoding"] == "utf-8"

    def test_latin1_content(self):
        data = "Name,City\nJosé,São Paulo\n".encode("latin-1")
        result = CSVExtractor().extract(data, "test.csv")

        assert "Jos" in result.text  # encoding detected (exact chars depend on detection)
        assert result.metadata["encoding"] != "utf-8"  # should detect non-utf8

    def test_metadata_fields(self):
        data = b"A,B\n1,2\n"
        result = CSVExtractor().extract(data, "test.csv")

        assert result.metadata["extractor"] == "csv"
        assert "encoding" in result.metadata
        assert "delimiter" in result.metadata
        assert result.page_count is None
        assert result.ocr_confidence is None
