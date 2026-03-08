"""Tests for LITIGAGENT ExcelExtractor (L2.6)."""

from __future__ import annotations

import io

import openpyxl

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.xlsx import ExcelExtractor


def _make_xlsx(sheets: dict[str, list[list]]) -> bytes:
    """Create an in-memory .xlsx file from a dict of sheet_name → rows."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- Interface tests ---


class TestExcelExtractorInterface:
    def test_can_extract_xlsx_extension(self):
        assert ExcelExtractor().can_extract("application/octet-stream", "xlsx") is True

    def test_can_extract_by_mime(self):
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert ExcelExtractor().can_extract(mime, "unknown") is True

    def test_cannot_extract_csv(self):
        assert ExcelExtractor().can_extract("text/csv", "csv") is False

    def test_cannot_extract_pdf(self):
        assert ExcelExtractor().can_extract("application/pdf", "pdf") is False

    def test_supported_extensions(self):
        assert ExcelExtractor().supported_extensions == {"xlsx"}

    def test_isinstance_file_extractor(self):
        assert isinstance(ExcelExtractor(), FileExtractor)


# --- Single sheet extraction ---


class TestExcelSingleSheet:
    def test_simple_table(self):
        data = _make_xlsx({"Sheet1": [["Name", "Age"], ["Alice", 30], ["Bob", 25]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert isinstance(result, ExtractionResult)
        assert "| Name | Age |" in result.text
        assert "| --- | --- |" in result.text
        assert "| Alice | 30 |" in result.text
        assert "| Bob | 25 |" in result.text
        assert result.metadata["extractor"] == "xlsx"
        assert result.metadata["sheet_count"] == 1
        assert result.warnings == []

    def test_single_sheet_no_heading(self):
        """Single sheet should not have a ## heading."""
        data = _make_xlsx({"Sheet1": [["A", "B"], [1, 2]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "## Sheet1" not in result.text
        assert "| A | B |" in result.text

    def test_numeric_values(self):
        data = _make_xlsx({"Data": [["X", "Y"], [1.5, 2.7], [3, 4]]})
        result = ExcelExtractor().extract(data, "numbers.xlsx")

        assert "| 1.5 | 2.7 |" in result.text
        assert "| 3 | 4 |" in result.text

    def test_none_cells(self):
        data = _make_xlsx({"Sheet1": [["A", "B"], [None, "val"], ["val2", None]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "| A | B |" in result.text
        assert "|  | val |" in result.text
        assert "| val2 |  |" in result.text

    def test_pipe_characters_escaped(self):
        data = _make_xlsx({"Sheet1": [["Col"], ["a|b"]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "a\\|b" in result.text


# --- Multiple sheets ---


class TestExcelMultiSheet:
    def test_two_sheets_have_headings(self):
        data = _make_xlsx({
            "Employees": [["Name", "Dept"], ["Alice", "Eng"]],
            "Salaries": [["Name", "Salary"], ["Alice", 100000]],
        })
        result = ExcelExtractor().extract(data, "multi.xlsx")

        assert "## Employees" in result.text
        assert "## Salaries" in result.text
        assert "| Alice | Eng |" in result.text
        assert "| Alice | 100000 |" in result.text
        assert result.metadata["sheet_count"] == 2
        assert result.metadata["sheet_names"] == ["Employees", "Salaries"]

    def test_empty_sheet_warned(self):
        data = _make_xlsx({
            "Data": [["A"], ["1"]],
            "Empty": [],
        })
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert any("Empty" in w and "empty" in w for w in result.warnings)
        assert "| A |" in result.text

    def test_mixed_empty_and_data_sheets(self):
        data = _make_xlsx({
            "Sheet1": [],
            "Sheet2": [["X"], ["Y"]],
            "Sheet3": [],
        })
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "| X |" in result.text
        assert len([w for w in result.warnings if "empty" in w]) == 2


# --- Edge cases ---


class TestExcelEdgeCases:
    def test_empty_bytes(self):
        result = ExcelExtractor().extract(b"", "empty.xlsx")

        assert result.text == ""
        assert "No text extracted" in result.warnings[0]
        assert result.metadata["sheet_count"] == 0

    def test_corrupt_file(self):
        result = ExcelExtractor().extract(b"not a valid xlsx", "bad.xlsx")

        assert result.text == ""
        assert any("Failed to open" in w for w in result.warnings)

    def test_all_empty_sheets(self):
        data = _make_xlsx({"Sheet1": [], "Sheet2": []})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert result.text == ""
        assert any("No text extracted" in w for w in result.warnings)

    def test_single_cell(self):
        data = _make_xlsx({"Sheet1": [["Hello"]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "| Hello |" in result.text

    def test_trailing_empty_rows_trimmed(self):
        data = _make_xlsx({"Sheet1": [["A"], ["B"], [None], [None]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        lines = [line for line in result.text.split("\n") if line.startswith("|")]
        # header + separator + 1 data row = 3 lines
        assert len(lines) == 3

    def test_trailing_empty_columns_trimmed(self):
        data = _make_xlsx({"Sheet1": [["A", None, None], ["B", None, None]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "| A |" in result.text
        # Should only have 1 column — "| A |" has 2 pipes
        header_line = result.text.split("\n")[0]
        assert header_line.strip() == "| A |"

    def test_newlines_in_cells_flattened(self):
        data = _make_xlsx({"Sheet1": [["Col"], ["line1\nline2"]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert "line1 line2" in result.text
        assert "line1\nline2" not in result.text

    def test_metadata_fields(self):
        data = _make_xlsx({"Sheet1": [["A", "B"], [1, 2], [3, 4]]})
        result = ExcelExtractor().extract(data, "test.xlsx")

        assert result.metadata["extractor"] == "xlsx"
        assert result.metadata["sheet_count"] == 1
        assert result.metadata["sheet_names"] == ["Sheet1"]
        assert result.page_count is None
        assert result.ocr_confidence is None
