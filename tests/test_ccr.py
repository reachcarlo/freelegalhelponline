"""Tests for the CCR Title 2 FEHA Regulations loader.

Uses respx for HTTP mocking and follows the test_dlse_manual.py pattern.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from employee_help.scraper.extractors.ccr import (
    CORNELL_BASE_URL,
    FEHA_ARTICLES,
    CCRArticle,
    CCRLoader,
    CCRSection,
    get_all_section_numbers,
    get_article_for_section,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def loader(tmp_path):
    return CCRLoader(rate_limit=0.0, timeout=10.0, cache_dir=tmp_path / "ccr")


def _make_section_html(
    section_number: str = "11068",
    title: str = "Reasonable Accommodation",
    body_subdivisions: list[str] | None = None,
    notes: str = "",
    skip_marker: str | None = None,
) -> str:
    """Build a mock Cornell LII regulation page HTML."""
    h1_title = f"Cal. Code Regs. Tit. 2, § {section_number} - {title}"
    if skip_marker:
        h1_title += f" [{skip_marker}]"

    subdivisions = body_subdivisions or [
        "(a) Affirmative Duty. An employer has an affirmative duty to make reasonable accommodation.",
        "(b) No elimination of essential job function. Quality standards need not be lowered.",
    ]

    subsect_divs = "\n".join(
        f'<div class="subsect indent0">{s}</div>' for s in subdivisions
    )

    notes_html = ""
    if notes:
        notes_html = f'<div class="statereg-notes">{notes}</div>'
    else:
        notes_html = """
        <div class="statereg-notes">
            Note: Authority cited: Section 12935(a), Government Code.
            Reference: Sections 12920, 12921, 12926, 12926.1 and 12940, Government Code.
        </div>
        """

    return f"""
    <html>
    <head><title>{h1_title}</title></head>
    <body>
        <h1>{h1_title}</h1>
        <div class="statereg-text">
            {subsect_divs}
        </div>
        {notes_html}
    </body>
    </html>
    """


def _make_empty_section_html(section_number: str = "11000") -> str:
    """Build a mock page with h1 but no statereg-text div."""
    return f"""
    <html>
    <body>
        <h1>Cal. Code Regs. Tit. 2, § {section_number} - Some Title</h1>
    </body>
    </html>
    """


# ── Manifest Tests ────────────────────────────────────────────


class TestCCRArticleManifest:
    """Tests for the FEHA_ARTICLES manifest completeness."""

    def test_manifest_has_expected_articles(self):
        """Should have 11 articles (1, 2, 4-11 including 9.5)."""
        assert len(FEHA_ARTICLES) == 11

    def test_article_3_not_present(self):
        """Article 3 is reserved — should not be in manifest."""
        numbers = [a.number for a in FEHA_ARTICLES]
        assert 3 not in numbers

    def test_no_duplicate_sections(self):
        """No section number should appear in multiple articles."""
        all_nums = get_all_section_numbers()
        assert len(all_nums) == len(set(all_nums)), f"Duplicates found: {[n for n in all_nums if all_nums.count(n) > 1]}"

    def test_total_section_count(self):
        """Expect roughly 70-90 sections across all articles."""
        all_nums = get_all_section_numbers()
        assert 60 <= len(all_nums) <= 100

    def test_each_article_has_sections(self):
        """Every article in the manifest should have at least one section."""
        for article in FEHA_ARTICLES:
            assert len(article.sections) > 0, f"Art. {article.number} has no sections"

    def test_get_article_for_section_found(self):
        """Should return correct article for a known section."""
        article = get_article_for_section("11068")
        assert article is not None
        assert article.number == 5
        assert "Reasonable Accommodation" in article.name

    def test_get_article_for_section_not_found(self):
        """Should return None for an unknown section."""
        assert get_article_for_section("99999") is None


# ── Parse Section Page Tests ─────────────────────────────────


class TestParseSectionPage:
    """Tests for CCRLoader._parse_section_page()."""

    def test_parses_title(self, loader):
        html = _make_section_html("11068", "Reasonable Accommodation")
        article = CCRArticle(number=5, name="Reasonable Accommodation and Interactive Process", sections=["11068"])
        section = loader._parse_section_page(html, "11068", article)
        assert section is not None
        assert section.title == "Reasonable Accommodation"

    def test_parses_body_text(self, loader):
        html = _make_section_html("11068", "Reasonable Accommodation")
        article = CCRArticle(number=5, name="Test", sections=["11068"])
        section = loader._parse_section_page(html, "11068", article)
        assert section is not None
        assert "(a) Affirmative Duty" in section.text
        assert "(b) No elimination" in section.text

    def test_parses_multiple_subdivisions(self, loader):
        subdivisions = [
            "(a) First subdivision text.",
            "(b) Second subdivision text.",
            "(c) Third subdivision text.",
        ]
        html = _make_section_html("11064", "Interactive Process", body_subdivisions=subdivisions)
        article = CCRArticle(number=5, name="Test", sections=["11064"])
        section = loader._parse_section_page(html, "11064", article)
        assert section is not None
        assert "(a) First" in section.text
        assert "(c) Third" in section.text

    def test_skips_renumbered_section(self, loader):
        html = _make_section_html("7286.5", "Definitions", skip_marker="Renumbered")
        section = loader._parse_section_page(html, "7286.5", None)
        assert section is None

    def test_skips_reserved_section(self, loader):
        html = _make_section_html("11055", "Reserved", skip_marker="Reserved")
        section = loader._parse_section_page(html, "11055", None)
        assert section is None

    def test_returns_none_for_no_body(self, loader):
        html = _make_empty_section_html("11000")
        section = loader._parse_section_page(html, "11000", None)
        assert section is None

    def test_returns_none_for_no_h1(self, loader):
        html = "<html><body><p>No heading</p></body></html>"
        section = loader._parse_section_page(html, "11000", None)
        assert section is None

    def test_parses_authority_and_reference(self, loader):
        notes = """
        <div class="statereg-note">
            Note: Authority cited: Section 12935(a), Government Code.
            Reference: Sections 12920, 12921, and 12940, Government Code.
        </div>
        """
        html = _make_section_html("11068", "Test", notes=notes)
        article = CCRArticle(number=5, name="Test", sections=["11068"])
        section = loader._parse_section_page(html, "11068", article)
        assert section is not None
        assert "12935(a)" in section.authority
        assert "12920" in section.reference


# ── Fetch Section Tests ──────────────────────────────────────


class TestFetchSection:
    """Tests for CCRLoader.fetch_section() with HTTP mocking."""

    @respx.mock
    def test_fetch_success(self, loader):
        html = _make_section_html("11068", "Reasonable Accommodation")
        url = f"{CORNELL_BASE_URL}/2-CCR-11068"
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        with httpx.Client(follow_redirects=True) as client:
            section = loader.fetch_section("11068", client)

        assert section is not None
        assert section.number == "11068"
        assert section.title == "Reasonable Accommodation"

    @respx.mock
    def test_fetch_404_returns_none(self, loader):
        url = f"{CORNELL_BASE_URL}/2-CCR-99999"
        respx.get(url).mock(return_value=httpx.Response(404))

        with httpx.Client(follow_redirects=True) as client:
            section = loader.fetch_section("99999", client)

        assert section is None

    @respx.mock
    def test_fetch_caches_html(self, loader):
        html = _make_section_html("11068", "Reasonable Accommodation")
        url = f"{CORNELL_BASE_URL}/2-CCR-11068"
        route = respx.get(url).mock(return_value=httpx.Response(200, text=html))

        with httpx.Client(follow_redirects=True) as client:
            # First fetch — hits network
            section1 = loader.fetch_section("11068", client)
            assert route.call_count == 1

            # Second fetch — should use cache
            section2 = loader.fetch_section("11068", client)
            assert route.call_count == 1  # No additional request

        assert section1 is not None
        assert section2 is not None
        assert section1.title == section2.title

    @respx.mock
    def test_fetch_server_error_returns_none(self, loader):
        url = f"{CORNELL_BASE_URL}/2-CCR-11068"
        respx.get(url).mock(return_value=httpx.Response(500))

        with httpx.Client(follow_redirects=True) as client:
            section = loader.fetch_section("11068", client)

        assert section is None


# ── StatuteSection Conversion Tests ──────────────────────────


class TestToStatuteSections:
    """Tests for CCRLoader.to_statute_sections()."""

    def _make_ccr_sections(self) -> list[CCRSection]:
        art5 = CCRArticle(number=5, name="Reasonable Accommodation and Interactive Process", sections=["11068", "11069"])
        return [
            CCRSection(
                number="11068",
                title="Reasonable Accommodation",
                text="(a) Affirmative duty text.\n\n(b) No elimination text.",
                article=art5,
                authority="Section 12935(a), Government Code",
                reference="Sections 12920, 12921, Government Code",
            ),
            CCRSection(
                number="11069",
                title="Interactive Process",
                text="(a) When applicant or employee requests accommodation.",
                article=art5,
                authority="Section 12935(a), Government Code",
                reference="Sections 12926, 12940, Government Code",
            ),
        ]

    def test_converts_sections(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert len(results) == 2

    def test_citation_format(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert results[0].citation == "2 CCR § 11068"
        assert results[1].citation == "2 CCR § 11069"

    def test_code_abbreviation(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert results[0].code_abbreviation == "2-CCR"

    def test_heading_path_format(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        hp = results[0].heading_path
        assert hp.startswith("CCR Title 2 > FEHA Regulations >")
        assert "Art. 5" in hp
        assert "§ 11068 Reasonable Accommodation" in hp

    def test_source_url_format(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert results[0].source_url == f"{CORNELL_BASE_URL}/2-CCR-11068"

    def test_unique_source_urls(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        urls = [s.source_url for s in results]
        assert len(set(urls)) == len(urls)

    def test_includes_authority_in_text(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert "Authority cited:" in results[0].text
        assert "12935(a)" in results[0].text

    def test_includes_reference_in_text(self, loader):
        ccr_sections = self._make_ccr_sections()
        results = loader.to_statute_sections(ccr_sections)
        assert "Reference:" in results[0].text
        assert "12920" in results[0].text


# ── Config Tests ──────────────────────────────────────────────


class TestCCRConfig:
    """Tests for YAML configuration loading and validation."""

    def test_config_loads_from_yaml(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title2_feha.yaml")
        assert config.slug == "ccr_title2_feha"
        assert config.source_type.value == "statutory_code"
        assert config.statutory is not None
        assert config.statutory.method == "ccr_web"
        assert config.statutory.code_abbreviation == "2-CCR"

    def test_content_category_is_regulation(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title2_feha.yaml")
        assert config.extraction.content_category == "regulation"

    def test_content_category_enum_exists(self):
        from employee_help.storage.models import ContentCategory

        cat = ContentCategory("regulation")
        assert cat == ContentCategory.REGULATION

    def test_method_validation_accepts_ccr_web(self):
        """ccr_web should be a valid method in the whitelist."""
        from employee_help.config import load_source_config

        # Should not raise
        config = load_source_config("config/sources/ccr_title2_feha.yaml")
        assert config.statutory.method == "ccr_web"


# ── Retrieval Tests ───────────────────────────────────────────


class TestRegulationRetrieval:
    """Tests for regulation content in retrieval service."""

    def test_regulation_in_consumer_categories(self):
        from employee_help.retrieval.service import CONSUMER_CATEGORIES

        assert "regulation" in CONSUMER_CATEGORIES

    def test_attorney_mode_regulation_boost(self):
        """Attorney mode should boost regulation content by 1.2x."""
        from unittest.mock import MagicMock

        from employee_help.retrieval.service import RetrievalResult, RetrievalService

        service = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )

        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="Test regulation content",
            heading_path="CCR Title 2 > ...",
            content_category="regulation",
            citation="2 CCR § 11068",
            relevance_score=1.0,
        )

        processed = MagicMock()
        processed.has_citation = False
        processed.cited_section = None

        service._apply_mode_scoring([candidate], "attorney", processed)
        assert candidate.relevance_score == pytest.approx(1.2, rel=1e-6)

    def test_consumer_mode_no_regulation_boost(self):
        """Consumer mode should not apply any boost."""
        from unittest.mock import MagicMock

        from employee_help.retrieval.service import RetrievalResult, RetrievalService

        service = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )

        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="Test regulation content",
            heading_path="CCR Title 2 > ...",
            content_category="regulation",
            citation="2 CCR § 11068",
            relevance_score=1.0,
        )

        processed = MagicMock()
        processed.has_citation = False

        service._apply_mode_scoring([candidate], "consumer", processed)
        assert candidate.relevance_score == 1.0


# ── Live Tests (slow marker) ─────────────────────────────────


@pytest.mark.slow
class TestCCRLive:
    """Integration tests that fetch from Cornell LII.

    Only run with: pytest -m slow
    """

    def test_fetch_section_11068(self):
        """Live fetch of Reasonable Accommodation regulation."""
        loader = CCRLoader(cache_dir=Path("data/ccr"))
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal-research)"},
        ) as client:
            section = loader.fetch_section("11068", client)

        assert section is not None
        assert section.title == "Reasonable Accommodation"
        assert "(a)" in section.text
        assert "Affirmative Duty" in section.text

    def test_renumbered_section_returns_none(self):
        """Live fetch of a renumbered section should return None."""
        loader = CCRLoader(cache_dir=Path("data/ccr"))
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal-research)"},
        ) as client:
            section = loader.fetch_section("7286.5", client)

        assert section is None
