"""Tests for the CCR Title 8 (Industrial Relations) loader.

Uses respx to mock httpx HTTP calls. Covers TOC crawler, section parser,
StatuteSection conversion, regex patterns, config integration, and full pipeline.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from employee_help.scraper.extractors.ccr_title8 import (
    BASE_URL,
    FIGURE_TABLE_RE,
    MAX_TOC_DEPTH,
    REPEALED_RE,
    RESERVED_RE,
    SECTION_URL_RE,
    TITLE_URL,
    TOC_CHILD_RE,
    CCRTitle8Loader,
    CCRTitle8TOCCrawler,
    SectionMeta,
)


# ── Mock HTML Fixtures ───────────────────────────────────────


TITLE_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/title-8/division-1">Division 1 - Department of Industrial Relations (Chapter 1 to 8)</a></li>
<li><a href="/regulations/california/title-8/division-2">Division 2 - Agricultural Labor Relations Board (Chapter 1 to 12)</a></li>
<li><a href="/regulations/california/title-8/division-3">Division 3 - Public Employment Relations Board (Chapter 1 to 10)</a></li>
</ol>
</body></html>
"""

DIVISION_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/title-8/division-1/chapter-4">Chapter 4 - Division of Industrial Safety (Subchapter 1 to 21)</a></li>
<li><a href="/regulations/california/title-8/division-1/chapter-5">Chapter 5 - Industrial Welfare Commission (Group 1 to 4)</a></li>
</ol>
</body></html>
"""

CHAPTER_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/title-8/division-1/chapter-4/subchapter-7">Subchapter 7 - General Industry Safety Orders (Group 1 to 27)</a></li>
</ol>
</body></html>
"""

SUBCHAPTER_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1">Group 1 - General Physical Conditions and Structures (Article 1 to 6)</a></li>
<li><a href="/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-13">Group 13 - Cranes and Other Hoisting Equipment [Repealed]</a></li>
</ol>
</body></html>
"""

GROUP_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-1">Article 1 - Definitions (§ 3207)</a></li>
<li><a href="/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-4">Article 4 - Access, Work Space, and Work Areas (§ 3270 to 3280)</a></li>
</ol>
</body></html>
"""

ARTICLE_TOC_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/8-CCR-3207">§ 3207 - Definitions</a></li>
</ol>
</body></html>
"""

ARTICLE_MULTI_SECTIONS_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/8-CCR-3270">§ 3270 - Emergency Action Plan</a></li>
<li><a href="/regulations/california/8-CCR-3271">§ 3271 - Fire Prevention Plan</a></li>
<li><a href="/regulations/california/8-CCR-3272">§ 3272 - Housekeeping [Repealed]</a></li>
<li><a href="/regulations/california/8-CCR-3273">§ 3273 - Storage [Reserved]</a></li>
<li><a href="/regulations/california/8-CCR-3280">§ 3280 - Illumination</a></li>
</ol>
</body></html>
"""

ARTICLE_WITH_FIGURES_HTML = """
<html><body>
<ol>
<li><a href="/regulations/california/8-CCR-3207">§ 3207 - Definitions</a></li>
<li><a href="/regulations/california/8-CCR-3207-figure-1">Figure 1 - Diagram of Equipment</a></li>
<li><a href="/regulations/california/8-CCR-3207-table-A">Table A - Measurements</a></li>
<li><a href="/regulations/california/8-CCR-3208">§ 3208 - Referenced Standards</a></li>
</ol>
</body></html>
"""

SECTION_PAGE_HTML = """
<html>
<head><title>Cal. Code Regs. Tit. 8, § 3207 - Definitions</title></head>
<body>
<nav><a href="/">LII</a> <a href="/regulations/california">California</a></nav>
<main>
<article>
<h1>Cal. Code Regs. Tit. 8, § 3207 - Definitions</h1>
<div class="field-name-body">
<p><strong>Accident.</strong> An unexpected, unintended event that causes injury, illness, or damage.</p>
<p><strong>Approved.</strong> Acceptable to the Division after review and evaluation.</p>
<p><strong>Competent Person.</strong> A person who is capable of identifying existing hazards.</p>
<p>Authority cited: Section 142.3, Labor Code</p>
<p>Reference: Section 142.3, Labor Code</p>
</div>
</article>
</main>
</body></html>
"""

SECTION_PAGE_NO_AUTH_HTML = """
<html>
<head><title>Cal. Code Regs. Tit. 8, § 11040</title></head>
<body>
<main>
<article>
<h1>Cal. Code Regs. Tit. 8, § 11040</h1>
<div class="field-name-body">
<p>Every employer shall pay to each employee wages not less than the applicable minimum wage.</p>
<p>Hours worked in excess of eight hours in one workday shall be compensated at overtime rates.</p>
</div>
</article>
</main>
</body></html>
"""

SECTION_PAGE_EMPTY_HTML = """
<html>
<head><title>Cal. Code Regs. Tit. 8, § 9999</title></head>
<body>
<main>
<article>
<h1>Cal. Code Regs. Tit. 8, § 9999</h1>
<div class="field-name-body">
</div>
</article>
</main>
</body></html>
"""

WAGE_ORDER_HTML = """
<html>
<head><title>Cal. Code Regs. Tit. 8, § 11040 - Order Regulating Wages</title></head>
<body>
<main>
<article>
<h1>Cal. Code Regs. Tit. 8, § 11040 - Order Regulating Wages</h1>
<div class="field-name-body">
<p>Every employer shall pay to each employee wages not less than the minimum wage.</p>
<p>Hours worked in excess of eight hours in one workday shall be compensated at 1.5x.</p>
<p>Authority cited: Section 1173, Labor Code; and California Constitution, Article XIV, Section 1</p>
<p>Reference: Sections 1182 and 1184, Labor Code</p>
</div>
</article>
</main>
</body></html>
"""


# ── Regex Tests ──────────────────────────────────────────────


class TestRegexPatterns:
    """Tests for URL and text-matching regex patterns."""

    def test_section_url_matches_simple(self):
        m = SECTION_URL_RE.search("/regulations/california/8-CCR-3207")
        assert m is not None
        assert m.group(1) == "3207"

    def test_section_url_matches_dotted(self):
        m = SECTION_URL_RE.search("/regulations/california/8-CCR-11040.1")
        assert m is not None
        assert m.group(1) == "11040.1"

    def test_section_url_matches_double_dotted(self):
        m = SECTION_URL_RE.search("/regulations/california/8-CCR-3207.1.5")
        assert m is not None
        assert m.group(1) == "3207.1.5"

    def test_section_url_no_match_on_toc(self):
        assert SECTION_URL_RE.search("/regulations/california/title-8/division-1") is None

    def test_section_url_no_match_partial(self):
        assert SECTION_URL_RE.search("/regulations/california/8-CCR-3207/extra") is None

    def test_toc_child_matches_division(self):
        assert TOC_CHILD_RE.search("/regulations/california/title-8/division-1") is not None

    def test_toc_child_matches_chapter(self):
        assert TOC_CHILD_RE.search("/regulations/california/title-8/division-1/chapter-4") is not None

    def test_toc_child_matches_subchapter(self):
        url = "/regulations/california/title-8/division-1/chapter-4/subchapter-7"
        assert TOC_CHILD_RE.search(url) is not None

    def test_toc_child_matches_group(self):
        url = "/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1"
        assert TOC_CHILD_RE.search(url) is not None

    def test_toc_child_matches_article(self):
        url = "/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-1"
        assert TOC_CHILD_RE.search(url) is not None

    def test_toc_child_no_match_on_section(self):
        assert TOC_CHILD_RE.search("/regulations/california/8-CCR-3207") is None

    def test_figure_detection(self):
        assert FIGURE_TABLE_RE.search("Figure 1 - Diagram") is not None
        assert FIGURE_TABLE_RE.search("Table A - Measurements") is not None
        assert FIGURE_TABLE_RE.search("Appendix B") is not None

    def test_figure_no_false_positive(self):
        assert FIGURE_TABLE_RE.search("§ 3207 - Definitions") is None

    def test_repealed_detection(self):
        assert REPEALED_RE.search("§ 3272 - Housekeeping [Repealed]") is not None

    def test_repealed_no_false_positive(self):
        assert REPEALED_RE.search("§ 3207 - Definitions") is None

    def test_reserved_detection(self):
        assert RESERVED_RE.search("§ 3273 - Storage [Reserved]") is not None

    def test_reserved_no_false_positive(self):
        assert RESERVED_RE.search("§ 3207 - Definitions") is None


# ── TOC Crawler Tests ────────────────────────────────────────


class TestCCRTitle8TOCCrawler:
    """Tests for recursive TOC discovery."""

    def test_extract_links_from_html(self):
        crawler = CCRTitle8TOCCrawler(rate_limit=0)
        links = crawler._extract_links(TITLE_TOC_HTML)
        hrefs = [href for href, _ in links]
        assert any("/division-1" in h for h in hrefs)
        assert any("/division-2" in h for h in hrefs)

    def test_extract_links_empty_html(self):
        crawler = CCRTitle8TOCCrawler(rate_limit=0)
        links = crawler._extract_links("<html><body></body></html>")
        assert links == []

    @respx.mock
    def test_crawl_finds_section_links(self, tmp_path):
        """Crawling an article page should find section links."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-1"
        respx.get(url).mock(return_value=httpx.Response(200, text=ARTICLE_TOC_HTML))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(url, client, ["Division 1"])
        finally:
            client.close()

        assert len(sections) == 1
        assert sections[0].section_number == "3207"
        assert sections[0].title == "Definitions"

    @respx.mock
    def test_crawl_detects_repealed(self, tmp_path):
        """Repealed sections should be flagged."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-4"
        respx.get(url).mock(return_value=httpx.Response(200, text=ARTICLE_MULTI_SECTIONS_HTML))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(url, client, ["Division 1"])
        finally:
            client.close()

        repealed = [s for s in sections if s.is_repealed]
        assert len(repealed) == 1
        assert repealed[0].section_number == "3272"

    @respx.mock
    def test_crawl_skips_reserved(self, tmp_path):
        """Reserved sections should be omitted entirely."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-4"
        respx.get(url).mock(return_value=httpx.Response(200, text=ARTICLE_MULTI_SECTIONS_HTML))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(url, client, ["Division 1"])
        finally:
            client.close()

        numbers = [s.section_number for s in sections]
        assert "3273" not in numbers

    @respx.mock
    def test_crawl_skips_figures(self, tmp_path):
        """Figure and table links should be skipped."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-1"
        respx.get(url).mock(return_value=httpx.Response(200, text=ARTICLE_WITH_FIGURES_HTML))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(url, client, ["Division 1"])
        finally:
            client.close()

        numbers = [s.section_number for s in sections]
        assert "3207" in numbers
        assert "3208" in numbers
        # Figures/tables should not appear as sections
        assert len(sections) == 2

    @respx.mock
    def test_crawl_recursive_hierarchy(self, tmp_path):
        """Crawler should follow TOC links recursively from chapter -> subchapter -> group -> article -> sections."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)

        chapter_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4"
        sub_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7"
        group_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1"
        article1_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-1"
        article4_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4/subchapter-7/group-1/article-4"

        respx.get(chapter_url).mock(return_value=httpx.Response(200, text=CHAPTER_TOC_HTML))
        respx.get(sub_url).mock(return_value=httpx.Response(200, text=SUBCHAPTER_TOC_HTML))
        respx.get(group_url).mock(return_value=httpx.Response(200, text=GROUP_TOC_HTML))
        respx.get(article1_url).mock(return_value=httpx.Response(200, text=ARTICLE_TOC_HTML))
        respx.get(article4_url).mock(return_value=httpx.Response(200, text=ARTICLE_MULTI_SECTIONS_HTML))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(chapter_url, client, ["Division 1"])
        finally:
            client.close()

        assert len(sections) >= 1
        assert sections[0].section_number == "3207"
        # Hierarchy should include intermediate levels
        assert len(sections[0].hierarchy_path) > 1

    @respx.mock
    def test_crawl_depth_limit(self, tmp_path):
        """Crawler should stop at MAX_TOC_DEPTH to prevent infinite loops."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)

        url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(url).mock(return_value=httpx.Response(200, text=DIVISION_TOC_HTML))

        client = httpx.Client()
        try:
            # Call at depth MAX_TOC_DEPTH + 1 — should return empty
            sections = crawler._crawl_toc_recursive(
                url, client, ["Division 1"], depth=MAX_TOC_DEPTH + 1
            )
        finally:
            client.close()

        assert sections == []

    @respx.mock
    def test_crawl_handles_http_error(self, tmp_path):
        """HTTP errors during TOC crawling should be handled gracefully."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(url).mock(return_value=httpx.Response(500))

        client = httpx.Client()
        try:
            sections = crawler._crawl_toc_recursive(url, client, ["Division 1"])
        finally:
            client.close()

        assert sections == []

    def test_fetch_page_caches_locally(self, tmp_path):
        """Fetched pages should be saved to the local cache."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/title-8"

        with respx.mock:
            respx.get(url).mock(
                return_value=httpx.Response(200, text="<html>cached</html>")
            )
            client = httpx.Client()
            try:
                html1 = crawler._fetch_page(url, client)
            finally:
                client.close()

        assert "cached" in html1
        # Cache file should exist
        cache_files = list(tmp_path.glob("*.html"))
        assert len(cache_files) == 1

    def test_fetch_page_uses_cache(self, tmp_path):
        """Second fetch should read from cache, not make HTTP request."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)

        # Pre-populate cache
        cache_file = tmp_path / "regulations_california_title-8.html"
        cache_file.write_text("<html>from cache</html>")

        url = f"{BASE_URL}/regulations/california/title-8"

        with respx.mock:
            # No HTTP routes needed — should read from cache
            client = httpx.Client()
            try:
                html = crawler._fetch_page(url, client)
            finally:
                client.close()

        assert "from cache" in html

    @respx.mock
    def test_discover_filters_by_division(self, tmp_path):
        """discover() should only crawl target divisions."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)

        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))

        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(div1_url).mock(return_value=httpx.Response(200, text="<html><body></body></html>"))

        # Division 2 and 3 should NOT be fetched
        client = httpx.Client()
        try:
            sections = crawler.discover(target_divisions=["1"], client=client)
        finally:
            client.close()

        # Verify only division 1 was accessed (no errors from missing div 2/3 routes)
        assert isinstance(sections, list)

    @respx.mock
    def test_discover_deduplicates(self, tmp_path):
        """Sections appearing in multiple articles should be deduplicated."""
        crawler = CCRTitle8TOCCrawler(cache_dir=tmp_path, rate_limit=0)

        # Set up a hierarchy that has the same section in two places
        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))

        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        # Two chapter links that both lead to the same section
        dup_html = """
        <html><body>
        <li><a href="/regulations/california/title-8/division-1/chapter-4">Chapter 4</a></li>
        <li><a href="/regulations/california/title-8/division-1/chapter-5">Chapter 5</a></li>
        </body></html>
        """
        respx.get(div1_url).mock(return_value=httpx.Response(200, text=dup_html))

        ch4_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-4"
        ch5_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-5"

        # Both chapters have section 3207
        section_html = '<html><body><a href="/regulations/california/8-CCR-3207">§ 3207 - Definitions</a></body></html>'
        respx.get(ch4_url).mock(return_value=httpx.Response(200, text=section_html))
        respx.get(ch5_url).mock(return_value=httpx.Response(200, text=section_html))

        client = httpx.Client()
        try:
            sections = crawler.discover(target_divisions=["1"], client=client)
        finally:
            client.close()

        # Should be deduplicated to just 1
        assert len(sections) == 1
        assert sections[0].section_number == "3207"


# ── Section Parser Tests ─────────────────────────────────────


class TestSectionParser:
    """Tests for section page HTML parsing."""

    def test_parse_extracts_text(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_HTML)
        assert "unexpected, unintended event" in parsed["text"]
        assert "Competent Person" in parsed["text"]

    def test_parse_extracts_title(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_HTML)
        assert "3207" in parsed["title"]
        assert "Definitions" in parsed["title"]

    def test_parse_extracts_authority(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_HTML)
        assert "142.3" in parsed["authority"]

    def test_parse_extracts_reference(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_HTML)
        assert "142.3" in parsed["reference"]

    def test_parse_no_authority(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_NO_AUTH_HTML)
        assert parsed["authority"] == ""
        assert parsed["reference"] == ""

    def test_parse_empty_body(self):
        parsed = CCRTitle8Loader.parse_section_page(SECTION_PAGE_EMPTY_HTML)
        # Title should still be extracted
        assert "9999" in parsed["title"]

    def test_parse_wage_order(self):
        parsed = CCRTitle8Loader.parse_section_page(WAGE_ORDER_HTML)
        assert "minimum wage" in parsed["text"]
        assert "1173" in parsed["authority"]
        assert "1182" in parsed["reference"]


# ── StatuteSection Conversion Tests ──────────────────────────


class TestStatuteSectionConversion:
    """Tests for converting parsed data to StatuteSection objects."""

    def test_citation_format(self):
        loader = CCRTitle8Loader(rate_limit=0)
        meta = SectionMeta(
            section_number="3207",
            title="Definitions",
            url=f"{BASE_URL}/regulations/california/8-CCR-3207",
            hierarchy_path=["Division 1", "Chapter 4", "Subchapter 7"],
        )
        parsed = {"text": "Some regulatory text.", "title": "§ 3207", "authority": "", "reference": ""}
        section = loader._build_statute_section(meta, parsed)

        assert section.citation == "Cal. Code Regs. tit. 8, § 3207"

    def test_heading_path_format(self):
        loader = CCRTitle8Loader(rate_limit=0)
        meta = SectionMeta(
            section_number="3207",
            title="Definitions",
            url=f"{BASE_URL}/regulations/california/8-CCR-3207",
            hierarchy_path=["Division 1", "Chapter 4", "Subchapter 7"],
        )
        parsed = {"text": "Text.", "title": "§ 3207", "authority": "", "reference": ""}
        section = loader._build_statute_section(meta, parsed)

        assert section.heading_path == "CCR Title 8 > Division 1 > Chapter 4 > Subchapter 7 > § 3207 Definitions"

    def test_heading_path_no_title(self):
        loader = CCRTitle8Loader(rate_limit=0)
        meta = SectionMeta(
            section_number="3207",
            title="",
            url=f"{BASE_URL}/regulations/california/8-CCR-3207",
            hierarchy_path=["Division 1"],
        )
        parsed = {"text": "Text.", "title": "", "authority": "", "reference": ""}
        section = loader._build_statute_section(meta, parsed)

        assert section.heading_path == "CCR Title 8 > Division 1 > § 3207"

    def test_source_url(self):
        loader = CCRTitle8Loader(rate_limit=0)
        url = f"{BASE_URL}/regulations/california/8-CCR-3207"
        meta = SectionMeta(
            section_number="3207",
            title="Definitions",
            url=url,
            hierarchy_path=["Division 1"],
        )
        parsed = {"text": "Text.", "title": "", "authority": "", "reference": ""}
        section = loader._build_statute_section(meta, parsed)

        assert section.source_url == url

    def test_code_abbreviation(self):
        loader = CCRTitle8Loader(rate_limit=0)
        meta = SectionMeta(
            section_number="3207",
            title="Definitions",
            url="https://example.com",
            hierarchy_path=["Division 1"],
        )
        parsed = {"text": "Text.", "title": "", "authority": "", "reference": ""}
        section = loader._build_statute_section(meta, parsed)

        assert section.code_abbreviation == "8-CCR"

    def test_authority_appended_to_text(self):
        loader = CCRTitle8Loader(rate_limit=0)
        meta = SectionMeta(
            section_number="3207",
            title="Definitions",
            url="https://example.com",
            hierarchy_path=["Division 1"],
        )
        parsed = {
            "text": "Main text.",
            "title": "",
            "authority": "Section 142.3, Labor Code",
            "reference": "Section 142.3, Labor Code",
        }
        section = loader._build_statute_section(meta, parsed)

        assert "Authority: Section 142.3" in section.text
        assert "Reference: Section 142.3" in section.text
        assert section.text.startswith("Main text.")

    def test_each_section_unique_url(self):
        loader = CCRTitle8Loader(rate_limit=0)
        sections = []
        for num in ["3207", "3270", "3271"]:
            meta = SectionMeta(
                section_number=num,
                title=f"Section {num}",
                url=f"{BASE_URL}/regulations/california/8-CCR-{num}",
                hierarchy_path=["Division 1"],
            )
            parsed = {"text": f"Text for {num}.", "title": "", "authority": "", "reference": ""}
            sections.append(loader._build_statute_section(meta, parsed))

        urls = [s.source_url for s in sections]
        assert len(set(urls)) == 3


# ── Full Pipeline Tests ──────────────────────────────────────


class TestCCRTitle8Pipeline:
    """End-to-end tests with mocked HTTP."""

    @respx.mock
    def test_full_pipeline(self, tmp_path):
        """Full pipeline should discover and parse sections."""
        loader = CCRTitle8Loader(
            cache_dir=tmp_path,
            rate_limit=0,
            target_divisions=["1"],
        )

        # Set up complete mock hierarchy
        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))
        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        chapter_url = f"{BASE_URL}/regulations/california/title-8/division-1/chapter-5"
        respx.get(div1_url).mock(return_value=httpx.Response(200, text="""
        <html><body>
        <a href="/regulations/california/title-8/division-1/chapter-5">Chapter 5 - Industrial Welfare Commission</a>
        </body></html>
        """))
        respx.get(chapter_url).mock(return_value=httpx.Response(200, text="""
        <html><body>
        <a href="/regulations/california/8-CCR-11040">§ 11040 - Order Regulating Wages</a>
        </body></html>
        """))
        respx.get(f"{BASE_URL}/regulations/california/8-CCR-11040").mock(
            return_value=httpx.Response(200, text=WAGE_ORDER_HTML)
        )

        sections = loader.to_statute_sections()

        assert len(sections) == 1
        assert sections[0].citation == "Cal. Code Regs. tit. 8, § 11040"
        assert "minimum wage" in sections[0].text

    @respx.mock
    def test_pipeline_skips_repealed(self, tmp_path):
        """Repealed sections should be skipped."""
        loader = CCRTitle8Loader(
            cache_dir=tmp_path,
            rate_limit=0,
            target_divisions=["1"],
        )

        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))
        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(div1_url).mock(return_value=httpx.Response(200, text="""
        <html><body>
        <a href="/regulations/california/8-CCR-3207">§ 3207 - Definitions</a>
        <a href="/regulations/california/8-CCR-3272">§ 3272 - Housekeeping [Repealed]</a>
        </body></html>
        """))
        respx.get(f"{BASE_URL}/regulations/california/8-CCR-3207").mock(
            return_value=httpx.Response(200, text=SECTION_PAGE_HTML)
        )

        sections = loader.to_statute_sections()

        numbers = [s.section_number for s in sections]
        assert "3207" in numbers
        assert "3272" not in numbers

    @respx.mock
    def test_pipeline_handles_section_fetch_error(self, tmp_path):
        """Section fetch failures should be logged and skipped."""
        loader = CCRTitle8Loader(
            cache_dir=tmp_path,
            rate_limit=0,
            target_divisions=["1"],
        )

        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))
        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(div1_url).mock(return_value=httpx.Response(200, text="""
        <html><body>
        <a href="/regulations/california/8-CCR-3207">§ 3207 - Definitions</a>
        <a href="/regulations/california/8-CCR-3270">§ 3270 - Emergency Action Plan</a>
        </body></html>
        """))
        respx.get(f"{BASE_URL}/regulations/california/8-CCR-3207").mock(
            return_value=httpx.Response(200, text=SECTION_PAGE_HTML)
        )
        respx.get(f"{BASE_URL}/regulations/california/8-CCR-3270").mock(
            return_value=httpx.Response(500)
        )

        sections = loader.to_statute_sections()

        # Only section 3207 should succeed
        assert len(sections) == 1
        assert sections[0].section_number == "3207"

    @respx.mock
    def test_pipeline_skips_empty_sections(self, tmp_path):
        """Sections with no text should be skipped."""
        loader = CCRTitle8Loader(
            cache_dir=tmp_path,
            rate_limit=0,
            target_divisions=["1"],
        )

        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))
        div1_url = f"{BASE_URL}/regulations/california/title-8/division-1"
        respx.get(div1_url).mock(return_value=httpx.Response(200, text="""
        <html><body>
        <a href="/regulations/california/8-CCR-9999">§ 9999 - Empty</a>
        </body></html>
        """))
        respx.get(f"{BASE_URL}/regulations/california/8-CCR-9999").mock(
            return_value=httpx.Response(200, text=SECTION_PAGE_EMPTY_HTML)
        )

        sections = loader.to_statute_sections()
        assert len(sections) == 0

    @respx.mock
    def test_pipeline_returns_empty_when_no_discovery(self, tmp_path):
        """If TOC discovery finds nothing, return empty list."""
        loader = CCRTitle8Loader(
            cache_dir=tmp_path,
            rate_limit=0,
            target_divisions=["99"],  # Non-existent division
        )

        respx.get(TITLE_URL).mock(return_value=httpx.Response(200, text=TITLE_TOC_HTML))

        sections = loader.to_statute_sections()
        assert sections == []


# ── Config + Integration Tests ───────────────────────────────


class TestCCRTitle8Config:
    """Tests for CCR Title 8 configuration and integration."""

    def test_config_loads_from_yaml(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert config.slug == "ccr_title_8"
        assert config.source_type.value == "statutory_code"
        assert config.statutory is not None
        assert config.statutory.method == "ccr_title_8"
        assert config.statutory.code_abbreviation == "8-CCR"
        assert config.extraction.content_category == "regulation"

    def test_citation_prefix(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert config.statutory.citation_prefix == "Cal. Code Regs. tit. 8"

    def test_target_divisions(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert "1" in config.statutory.target_divisions

    def test_content_category_enum_exists(self):
        from employee_help.storage.models import ContentCategory

        cat = ContentCategory("regulation")
        assert cat == ContentCategory.REGULATION

    def test_regulation_in_consumer_categories(self):
        from employee_help.retrieval.service import CONSUMER_CATEGORIES

        assert "regulation" in CONSUMER_CATEGORIES

    def test_chunking_strategy(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert config.chunking.strategy == "section_boundary"
        assert config.chunking.max_tokens == 1500

    def test_rate_limit(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert config.rate_limit_seconds == 2.0


# ── Section Cache Tests ──────────────────────────────────────


class TestSectionCache:
    """Tests for the section page caching mechanism."""

    def test_section_cache_saves_file(self, tmp_path):
        loader = CCRTitle8Loader(cache_dir=tmp_path, rate_limit=0)
        url = f"{BASE_URL}/regulations/california/8-CCR-3207"

        with respx.mock:
            respx.get(url).mock(
                return_value=httpx.Response(200, text="<html>section content</html>")
            )
            client = httpx.Client()
            try:
                html = loader._fetch_section(url, client)
            finally:
                client.close()

        assert "section content" in html
        cache_files = list((tmp_path / "sections").glob("*.html"))
        assert len(cache_files) == 1
        assert "8-CCR-3207" in cache_files[0].name

    def test_section_cache_reads_existing(self, tmp_path):
        loader = CCRTitle8Loader(cache_dir=tmp_path, rate_limit=0)

        # Pre-populate cache
        sections_dir = tmp_path / "sections"
        sections_dir.mkdir()
        cache_file = sections_dir / "8-CCR-3207.html"
        cache_file.write_text("<html>cached section</html>")

        url = f"{BASE_URL}/regulations/california/8-CCR-3207"

        with respx.mock:
            # No HTTP route — should use cache
            client = httpx.Client()
            try:
                html = loader._fetch_section(url, client)
            finally:
                client.close()

        assert "cached section" in html


# ── Live Tests ───────────────────────────────────────────────


@pytest.mark.slow
class TestCCRTitle8Live:
    """Integration tests that fetch real pages from Cornell LII.

    Only run with: pytest -m slow
    """

    def test_title_page_has_divisions(self):
        client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal research tool)"},
        )
        try:
            resp = client.get(TITLE_URL)
            resp.raise_for_status()
            assert "division-1" in resp.text.lower() or "Division 1" in resp.text
        finally:
            client.close()

    def test_section_page_has_content(self):
        client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal research tool)"},
        )
        try:
            resp = client.get(f"{BASE_URL}/regulations/california/8-CCR-3207")
            resp.raise_for_status()
            parsed = CCRTitle8Loader.parse_section_page(resp.text)
            assert len(parsed["text"]) > 100
        finally:
            client.close()
