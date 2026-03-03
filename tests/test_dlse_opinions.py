"""Tests for the DLSE Opinion Letters loader.

Uses respx to mock httpx HTTP calls and unittest.mock for pdfplumber.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from employee_help.scraper.extractors.dlse_opinions import (
    INDEX_BY_DATE,
    INDEX_BY_SUBJECT,
    DLSEOpinionIndexScraper,
    DLSEOpinionLoader,
    OpinionLetterMeta,
)


# ── Fixtures ──────────────────────────────────────────────────


SUBJECT_HTML = """
<html><body>
<h2>Overtime</h2>
<table>
<tr><td><a href="/dlse/opinions/2019.01.03.pdf">2019.01.03</a></td><td>Overtime calculation for piece-rate</td></tr>
<tr><td><a href="/dlse/opinions/2018.06.15.pdf">2018.06.15</a></td><td>Overtime exemption for commissioned employees</td></tr>
</table>
<h2>Meal Periods</h2>
<table>
<tr><td><a href="/dlse/opinions/2017.03.22.pdf">2017.03.22</a></td><td>Meal period waiver requirements</td></tr>
<tr><td><a href="/dlse/opinions/2016.05.10.pdf">2016.05.10</a></td><td>Withdrawn - replaced by 2017.03.22</td></tr>
</table>
</body></html>
"""

DATE_HTML = """
<html><body>
<table>
<tr><td><a href="/dlse/opinions/2019.01.03.pdf">2019.01.03</a></td><td>Overtime</td></tr>
<tr><td><a href="/dlse/opinions/2015.09.01.pdf">2015.09.01</a></td><td>Tips and gratuities</td></tr>
<tr><td><a href="/dlse/opinions/2019.01.03-RL.pdf">2019.01.03-RL</a></td><td>Requesting letter</td></tr>
</table>
</body></html>
"""

EMPTY_TABLE_HTML = """
<html><body>
<table></table>
</body></html>
"""


@pytest.fixture
def scraper():
    return DLSEOpinionIndexScraper()


@pytest.fixture
def sample_letter():
    return OpinionLetterMeta(
        date="2019-01-03",
        pdf_url="https://www.dir.ca.gov/dlse/opinions/2019.01.03.pdf",
        subject="Overtime",
        description="Overtime calculation for piece-rate",
        filename="2019.01.03.pdf",
    )


# ── Index Scraper Tests ──────────────────────────────────────


class TestDLSEOpinionIndexScraper:
    """Tests for the HTML index page scraper."""

    def test_scrape_by_subject_extracts_letters(self, scraper):
        letters = scraper.scrape_by_subject(SUBJECT_HTML)
        # Should find 3 (skips withdrawn)
        assert len(letters) == 3
        assert letters[0].filename == "2019.01.03.pdf"
        assert letters[0].subject == "Overtime"
        assert letters[0].date == "2019-01-03"

    def test_scrape_by_subject_skips_withdrawn(self, scraper):
        letters = scraper.scrape_by_subject(SUBJECT_HTML)
        filenames = [l.filename for l in letters]
        assert "2016.05.10.pdf" not in filenames

    def test_scrape_by_subject_resolves_urls(self, scraper):
        letters = scraper.scrape_by_subject(SUBJECT_HTML)
        assert letters[0].pdf_url == "https://www.dir.ca.gov/dlse/opinions/2019.01.03.pdf"

    def test_scrape_by_date_extracts_letters(self, scraper):
        letters = scraper.scrape_by_date(DATE_HTML)
        # Should find 2 (skips -RL.pdf)
        assert len(letters) == 2
        filenames = [l.filename for l in letters]
        assert "2019.01.03.pdf" in filenames
        assert "2015.09.01.pdf" in filenames

    def test_scrape_by_date_skips_requesting_letters(self, scraper):
        letters = scraper.scrape_by_date(DATE_HTML)
        filenames = [l.filename for l in letters]
        assert "2019.01.03-RL.pdf" not in filenames

    def test_empty_table_produces_empty_list(self, scraper):
        letters = scraper.scrape_by_subject(EMPTY_TABLE_HTML)
        assert letters == []

    def test_empty_date_table_produces_empty_list(self, scraper):
        letters = scraper.scrape_by_date(EMPTY_TABLE_HTML)
        assert letters == []

    def test_relative_urls_resolved(self, scraper):
        html = """
        <html><body><table>
        <tr><td><a href="/dlse/opinions/2010.04.15.pdf">Letter</a></td></tr>
        </table></body></html>
        """
        letters = scraper.scrape_by_subject(html)
        assert len(letters) == 1
        assert letters[0].pdf_url.startswith("https://www.dir.ca.gov")

    @respx.mock
    def test_discover_deduplicates(self, scraper):
        """Letters on both pages should be deduplicated, preferring subject page."""
        respx.get(INDEX_BY_SUBJECT).mock(
            return_value=httpx.Response(200, text=SUBJECT_HTML)
        )
        respx.get(INDEX_BY_DATE).mock(
            return_value=httpx.Response(200, text=DATE_HTML)
        )

        client = httpx.Client()
        try:
            letters = scraper.discover(client=client)
        finally:
            client.close()

        filenames = [l.filename for l in letters]
        # 2019.01.03.pdf appears on both pages — should only appear once
        assert filenames.count("2019.01.03.pdf") == 1
        # Should prefer subject page entry (has "Overtime" subject)
        overtime_letter = [l for l in letters if l.filename == "2019.01.03.pdf"][0]
        assert overtime_letter.subject == "Overtime"

    @respx.mock
    def test_discover_handles_subject_404(self, scraper):
        """If subject page fails, still gets letters from date page."""
        respx.get(INDEX_BY_SUBJECT).mock(
            return_value=httpx.Response(404)
        )
        respx.get(INDEX_BY_DATE).mock(
            return_value=httpx.Response(200, text=DATE_HTML)
        )

        client = httpx.Client()
        try:
            letters = scraper.discover(client=client)
        finally:
            client.close()

        assert len(letters) >= 1  # At least the date page letters

    @respx.mock
    def test_discover_handles_both_pages_fail(self, scraper):
        """If both pages fail, returns empty list."""
        respx.get(INDEX_BY_SUBJECT).mock(
            return_value=httpx.Response(500)
        )
        respx.get(INDEX_BY_DATE).mock(
            return_value=httpx.Response(500)
        )

        client = httpx.Client()
        try:
            letters = scraper.discover(client=client)
        finally:
            client.close()

        assert letters == []

    def test_extract_date_dotted_filename(self):
        assert DLSEOpinionIndexScraper._extract_date("2019.01.03.pdf") == "2019-01-03"

    def test_extract_date_dashed_filename(self):
        assert DLSEOpinionIndexScraper._extract_date("2019-01-03.pdf") == "2019-01-03"

    def test_extract_date_no_match(self):
        assert DLSEOpinionIndexScraper._extract_date("unknown.pdf") == "unknown"


# ── Loader Tests ─────────────────────────────────────────────


class TestDLSEOpinionLoader:
    """Tests for PDF download, parsing, and conversion."""

    def test_download_pdfs_skips_existing(self, tmp_path, sample_letter):
        """Existing files should be skipped when skip_existing=True."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        # Create an existing file
        existing = tmp_path / sample_letter.filename
        existing.write_text("existing content")

        with respx.mock:
            # No HTTP call should be made
            downloaded = loader.download_pdfs([sample_letter], skip_existing=True)

        assert len(downloaded) == 1
        assert downloaded[0][1] == existing

    @respx.mock
    def test_download_pdfs_handles_http_error(self, tmp_path, sample_letter):
        """Failed downloads should be skipped gracefully."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        respx.get(sample_letter.pdf_url).mock(
            return_value=httpx.Response(500)
        )

        downloaded = loader.download_pdfs([sample_letter], skip_existing=False)
        assert len(downloaded) == 0

    @respx.mock
    def test_download_pdfs_saves_content(self, tmp_path, sample_letter):
        """Successfully downloaded PDFs should be written to disk."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        respx.get(sample_letter.pdf_url).mock(
            return_value=httpx.Response(200, content=b"%PDF-1.4 fake content")
        )

        downloaded = loader.download_pdfs([sample_letter], skip_existing=False)
        assert len(downloaded) == 1
        assert downloaded[0][1].exists()
        assert downloaded[0][1].read_bytes() == b"%PDF-1.4 fake content"

    def test_parse_pdf_extracts_text(self, tmp_path):
        """parse_pdf should extract text from a valid PDF."""
        # Create a minimal PDF-like mock
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is the opinion letter text."

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF")

        with patch("employee_help.scraper.extractors.dlse_opinions.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            text = DLSEOpinionLoader.parse_pdf(pdf_path)

        assert "This is the opinion letter text." in text

    def test_parse_pdf_returns_empty_for_image_pdf(self, tmp_path):
        """Image-only PDFs should return empty string."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        pdf_path = tmp_path / "image.pdf"
        pdf_path.write_bytes(b"%PDF")

        with patch("employee_help.scraper.extractors.dlse_opinions.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            text = DLSEOpinionLoader.parse_pdf(pdf_path)

        assert text == ""

    def test_parse_pdf_handles_exception(self, tmp_path):
        """pdfplumber exceptions should return empty string."""
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.write_bytes(b"not a pdf")

        with patch("employee_help.scraper.extractors.dlse_opinions.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.side_effect = Exception("corrupt file")
            text = DLSEOpinionLoader.parse_pdf(pdf_path)

        assert text == ""

    def test_extract_cited_statutes_labor_code_section(self):
        text = "As stated in Labor Code section 510, overtime is required."
        cites = DLSEOpinionLoader.extract_cited_statutes(text)
        assert any("510" in c for c in cites)

    def test_extract_cited_statutes_lab_code_symbol(self):
        text = "Pursuant to Lab. Code, § 1194, employees may recover."
        cites = DLSEOpinionLoader.extract_cited_statutes(text)
        assert any("1194" in c for c in cites)

    def test_extract_cited_statutes_government_code(self):
        text = "Under Government Code section 12940, discrimination is prohibited."
        cites = DLSEOpinionLoader.extract_cited_statutes(text)
        assert any("12940" in c for c in cites)

    def test_extract_cited_statutes_no_duplicates(self):
        text = "Labor Code section 510 and Labor Code section 510 again."
        cites = DLSEOpinionLoader.extract_cited_statutes(text)
        # Should appear only once
        matching = [c for c in cites if "510" in c]
        assert len(matching) == 1

    def test_strip_signature_sincerely(self):
        text = "The analysis shows that...\n\nSincerely,\n\nJohn Doe\nLabor Commissioner"
        stripped = DLSEOpinionLoader.strip_signature(text)
        assert "Sincerely" not in stripped
        assert "John Doe" not in stripped
        assert "analysis shows" in stripped

    def test_strip_signature_very_truly_yours(self):
        text = "In conclusion...\n\nVery truly yours,\n\nJane Smith"
        stripped = DLSEOpinionLoader.strip_signature(text)
        assert "Very truly yours" not in stripped
        assert "conclusion" in stripped

    def test_strip_signature_no_signature(self):
        text = "This letter has no signature block."
        stripped = DLSEOpinionLoader.strip_signature(text)
        assert stripped == text

    def test_build_statute_section_fields(self, sample_letter):
        loader = DLSEOpinionLoader()
        body = "The employer must pay overtime for hours worked beyond 8 in a day."
        section = loader._build_statute_section(sample_letter, body)

        assert section.section_number == "2019-01-03"
        assert section.code_abbreviation == "DLSE"
        assert "DLSE Opinion Letter 2019-01-03 (Overtime)" in section.citation
        assert section.source_url == sample_letter.pdf_url
        assert "DLSE Opinion Letter dated 2019-01-03" in section.text
        assert "Subject: Overtime" in section.text
        assert "employer must pay overtime" in section.text

    def test_heading_path_format(self, sample_letter):
        loader = DLSEOpinionLoader()
        body = "Some text."
        section = loader._build_statute_section(sample_letter, body)

        assert section.heading_path == "DLSE Opinion Letters > Overtime > 2019-01-03"

    def test_each_letter_unique_source_url(self):
        loader = DLSEOpinionLoader()
        letters = [
            OpinionLetterMeta(
                date="2019-01-03",
                pdf_url="https://www.dir.ca.gov/dlse/opinions/2019.01.03.pdf",
                subject="Overtime",
                description="Test",
                filename="2019.01.03.pdf",
            ),
            OpinionLetterMeta(
                date="2018-06-15",
                pdf_url="https://www.dir.ca.gov/dlse/opinions/2018.06.15.pdf",
                subject="Wages",
                description="Test",
                filename="2018.06.15.pdf",
            ),
        ]
        sections = [
            loader._build_statute_section(l, "text") for l in letters
        ]
        urls = [s.source_url for s in sections]
        assert len(set(urls)) == 2

    def test_to_statute_sections_skips_empty_pdfs(self, tmp_path):
        """Empty text PDFs should be skipped in the full pipeline."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        letters = [
            OpinionLetterMeta(
                date="2019-01-03",
                pdf_url="https://example.com/2019.01.03.pdf",
                subject="Overtime",
                description="Test",
                filename="2019.01.03.pdf",
            ),
        ]

        with (
            patch.object(loader, "discover_letters", return_value=letters),
            patch.object(loader, "download_pdfs", return_value=[(letters[0], tmp_path / "2019.01.03.pdf")]),
            patch.object(DLSEOpinionLoader, "parse_pdf", return_value=""),
        ):
            sections = loader.to_statute_sections()

        assert len(sections) == 0

    def test_to_statute_sections_processes_valid_pdfs(self, tmp_path):
        """Valid PDFs should be converted to StatuteSection objects."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        letters = [
            OpinionLetterMeta(
                date="2019-01-03",
                pdf_url="https://example.com/2019.01.03.pdf",
                subject="Overtime",
                description="Test",
                filename="2019.01.03.pdf",
            ),
        ]

        with (
            patch.object(loader, "discover_letters", return_value=letters),
            patch.object(loader, "download_pdfs", return_value=[(letters[0], tmp_path / "2019.01.03.pdf")]),
            patch.object(DLSEOpinionLoader, "parse_pdf", return_value="The employer must pay overtime.\n\nSincerely,\n\nCommissioner"),
        ):
            sections = loader.to_statute_sections()

        assert len(sections) == 1
        assert "Sincerely" not in sections[0].text
        assert "employer must pay overtime" in sections[0].text

    def test_to_statute_sections_returns_empty_when_no_letters(self, tmp_path):
        """No discovered letters should return empty list."""
        loader = DLSEOpinionLoader(download_dir=tmp_path, rate_limit=0)

        with patch.object(loader, "discover_letters", return_value=[]):
            sections = loader.to_statute_sections()

        assert sections == []


# ── Config + Integration Tests ───────────────────────────────


class TestDLSEOpinionConfig:
    """Tests for DLSE opinion letter configuration."""

    def test_config_loads_from_yaml(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/dlse_opinions.yaml")
        assert config.slug == "dlse_opinions"
        assert config.source_type.value == "statutory_code"
        assert config.statutory is not None
        assert config.statutory.method == "dlse_opinions"
        assert config.statutory.code_abbreviation == "DLSE"
        assert config.extraction.content_category == "opinion_letter"

    def test_content_category_enum_exists(self):
        from employee_help.storage.models import ContentCategory

        cat = ContentCategory("opinion_letter")
        assert cat == ContentCategory.OPINION_LETTER

    def test_opinion_letter_in_consumer_categories(self):
        from employee_help.retrieval.service import CONSUMER_CATEGORIES

        assert "opinion_letter" in CONSUMER_CATEGORIES


@pytest.mark.slow
class TestDLSEOpinionLive:
    """Integration tests that hit live DLSE index pages.

    Only run with: pytest -m slow
    """

    def test_discover_letters_from_live_index(self):
        scraper = DLSEOpinionIndexScraper()
        letters = scraper.discover()
        assert len(letters) > 50  # Expect 100+ active letters

    def test_all_letters_have_required_fields(self):
        scraper = DLSEOpinionIndexScraper()
        letters = scraper.discover()
        for letter in letters:
            assert letter.filename, f"Missing filename: {letter}"
            assert letter.pdf_url, f"Missing pdf_url: {letter}"
            assert letter.date, f"Missing date: {letter}"
            assert letter.pdf_url.startswith("https://"), f"Non-HTTPS URL: {letter.pdf_url}"
