"""Tests for E.7 — EEOC Guidance Knowledge Source.

Covers config loading, URL pattern matching, ContentCategory wiring,
retrieval service integration, and pipeline content-category override logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from employee_help.config import load_source_config
from employee_help.pipeline import Pipeline, classify_content_category
from employee_help.retrieval.service import CONSUMER_CATEGORIES, RetrievalResult, RetrievalService
from employee_help.storage.models import ContentCategory, ContentType, SourceType


# ── Config loading tests ────────────────────────────────────

EEOC_CONFIG_PATH = Path("config/sources/eeoc.yaml")


class TestEEOCConfig:

    @pytest.fixture
    def config(self):
        return load_source_config(EEOC_CONFIG_PATH)

    def test_config_loads(self, config):
        assert config is not None

    def test_source_slug(self, config):
        assert config.slug == "eeoc"

    def test_source_type_is_agency(self, config):
        assert config.source_type == SourceType.AGENCY

    def test_base_url(self, config):
        assert config.base_url == "https://www.eeoc.gov"

    def test_content_category_is_federal_guidance(self, config):
        assert config.extraction.content_category == "federal_guidance"

    def test_content_selector(self, config):
        assert config.extraction.content_selector == "#main-content"

    def test_rate_limit(self, config):
        assert config.rate_limit_seconds >= 3.0

    def test_max_pages(self, config):
        assert config.max_pages == 150

    def test_chunking_strategy(self, config):
        assert config.chunking.strategy == "heading_based"

    def test_chunking_tokens(self, config):
        assert config.chunking.min_tokens == 200
        assert config.chunking.max_tokens == 1500
        assert config.chunking.overlap_tokens == 100

    def test_has_seed_urls(self, config):
        assert len(config.seed_urls) >= 2

    def test_has_allowlist_patterns(self, config):
        assert len(config.allowlist_patterns) >= 1

    def test_has_blocklist_patterns(self, config):
        assert len(config.blocklist_patterns) >= 1


# ── URL pattern tests ───────────────────────────────────────


class TestEEOCURLPatterns:

    @pytest.fixture
    def config(self):
        return load_source_config(EEOC_CONFIG_PATH)

    @pytest.fixture
    def allowlist(self, config):
        return [re.compile(p) for p in config.allowlist_patterns]

    @pytest.fixture
    def blocklist(self, config):
        return [re.compile(p) for p in config.blocklist_patterns]

    def _matches_allowlist(self, url, allowlist):
        return any(p.search(url) for p in allowlist)

    def _matches_blocklist(self, url, blocklist):
        return any(p.search(url) for p in blocklist)

    # Allowed URLs
    def test_allows_guidance_page(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/laws/guidance/enforcement-guidance-disability-related-inquiries",
            allowlist,
        )

    def test_allows_policy_docs(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/policy/docs/race-color.html",
            allowlist,
        )

    def test_allows_types_discrimination(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/laws/types-discrimination",
            allowlist,
        )

    def test_allows_harassment_page(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/harassment",
            allowlist,
        )

    def test_allows_retaliation_page(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/retaliation",
            allowlist,
        )

    def test_allows_disability_discrimination(self, allowlist):
        assert self._matches_allowlist(
            "https://www.eeoc.gov/disability-discrimination",
            allowlist,
        )

    # Blocked URLs
    def test_blocks_newsroom(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/newsroom/press-release",
            blocklist,
        )

    def test_blocks_litigation(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/litigation-statistics",
            blocklist,
        )

    def test_blocks_federal_sector(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/federal-sector/management-directive",
            blocklist,
        )

    def test_blocks_spanish(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/es/discriminacion-por-edad",
            blocklist,
        )

    def test_blocks_pdf(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/laws/guidance/document.pdf",
            blocklist,
        )

    def test_blocks_foia(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/foia/requests",
            blocklist,
        )

    def test_blocks_statistics(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/statistics/charges",
            blocklist,
        )

    def test_blocks_about(self, blocklist):
        assert self._matches_blocklist(
            "https://www.eeoc.gov/about-eeoc/history",
            blocklist,
        )


# ── ContentCategory enum tests ──────────────────────────────


class TestFederalGuidanceCategory:

    def test_enum_exists(self):
        assert hasattr(ContentCategory, "FEDERAL_GUIDANCE")
        assert ContentCategory.FEDERAL_GUIDANCE.value == "federal_guidance"

    def test_enum_round_trip(self):
        assert ContentCategory("federal_guidance") == ContentCategory.FEDERAL_GUIDANCE

    def test_in_consumer_categories(self):
        assert "federal_guidance" in CONSUMER_CATEGORIES


# ── Retrieval service scoring tests ─────────────────────────


class TestFederalGuidanceRetrieval:

    def test_attorney_mode_boost(self):
        """Attorney mode should apply 1.1x boost to federal_guidance."""
        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="EEOC guidance on Title VII",
            heading_path="EEOC > Title VII",
            content_category="federal_guidance",
            citation=None,
            relevance_score=1.0,
        )
        processed = MagicMock()
        processed.has_citation = False
        processed.cited_section = None

        service = RetrievalService.__new__(RetrievalService)
        service.statutory_boost = 1.2
        service.citation_boost = 1.5
        service._apply_mode_scoring([candidate], "attorney", processed)

        assert candidate.relevance_score == pytest.approx(1.1)

    def test_consumer_mode_no_boost(self):
        """Consumer mode should not apply attorney boosts."""
        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="EEOC guidance on Title VII",
            heading_path="EEOC > Title VII",
            content_category="federal_guidance",
            citation=None,
            relevance_score=1.0,
        )
        processed = MagicMock()

        service = RetrievalService.__new__(RetrievalService)
        service.statutory_boost = 1.2
        service.citation_boost = 1.5
        service._apply_mode_scoring([candidate], "consumer", processed)

        assert candidate.relevance_score == pytest.approx(1.0)


# ── Pipeline content-category override tests ────────────────


class TestPipelineContentCategoryOverride:

    def test_config_category_used_for_non_faq_url(self):
        """When config sets federal_guidance, non-FAQ URLs use that category."""
        config = load_source_config(EEOC_CONFIG_PATH)

        # Simulate the override logic from _run_crawler
        config_category_str = config.extraction.content_category
        url = "https://www.eeoc.gov/laws/guidance/something"
        content_type = ContentType.HTML

        assert config_category_str == "federal_guidance"

        # Apply the override logic
        if config_category_str != "agency_guidance":
            try:
                base_category = ContentCategory(config_category_str)
            except ValueError:
                base_category = ContentCategory.AGENCY_GUIDANCE
            url_category = classify_content_category(url, content_type)
            if url_category in (ContentCategory.FAQ, ContentCategory.FACT_SHEET):
                content_category = url_category
            else:
                content_category = base_category
        else:
            content_category = classify_content_category(url, content_type)

        assert content_category == ContentCategory.FEDERAL_GUIDANCE

    def test_faq_url_overrides_config_category(self):
        """FAQ heuristic should still override federal_guidance config."""
        config = load_source_config(EEOC_CONFIG_PATH)
        config_category_str = config.extraction.content_category
        url = "https://www.eeoc.gov/laws/guidance/frequently-asked-questions"
        content_type = ContentType.HTML

        if config_category_str != "agency_guidance":
            try:
                base_category = ContentCategory(config_category_str)
            except ValueError:
                base_category = ContentCategory.AGENCY_GUIDANCE
            url_category = classify_content_category(url, content_type)
            if url_category in (ContentCategory.FAQ, ContentCategory.FACT_SHEET):
                content_category = url_category
            else:
                content_category = base_category
        else:
            content_category = classify_content_category(url, content_type)

        assert content_category == ContentCategory.FAQ

    def test_default_agency_guidance_unchanged(self):
        """Sources without content_category override use URL heuristic as before."""
        url = "https://www.dir.ca.gov/dlse/some-page.html"
        content_type = ContentType.HTML
        content_category = classify_content_category(url, content_type)
        assert content_category == ContentCategory.AGENCY_GUIDANCE

    def test_invalid_config_category_falls_back(self):
        """Invalid content_category string should fall back to AGENCY_GUIDANCE."""
        config_category_str = "nonexistent_category"
        url = "https://www.eeoc.gov/laws/guidance/something"
        content_type = ContentType.HTML

        if config_category_str != "agency_guidance":
            try:
                base_category = ContentCategory(config_category_str)
            except ValueError:
                base_category = ContentCategory.AGENCY_GUIDANCE
            url_category = classify_content_category(url, content_type)
            if url_category in (ContentCategory.FAQ, ContentCategory.FACT_SHEET):
                content_category = url_category
            else:
                content_category = base_category
        else:
            content_category = classify_content_category(url, content_type)

        assert content_category == ContentCategory.AGENCY_GUIDANCE


# ── HTML extractor content_selector tests ────────────────────


class TestContentSelector:

    def test_extract_html_with_content_selector(self):
        """content_selector should be used as authoritative main element."""
        from employee_help.scraper.extractors.html import extract_html

        html = """
        <html>
        <body>
            <div id="sidebar">Sidebar noise</div>
            <div id="main-content">
                <h1>Title VII Guidance</h1>
                <p>Important EEOC guidance content.</p>
            </div>
        </body>
        </html>
        """
        result = extract_html(html, "https://www.eeoc.gov/test", content_selector="#main-content")
        assert "Important EEOC guidance content" in result.markdown
        # Sidebar should not be included since #main-content was found
        assert "Sidebar noise" not in result.markdown

    def test_extract_html_without_content_selector_uses_fallback(self):
        """Without content_selector, should fall back to default chain."""
        from employee_help.scraper.extractors.html import extract_html

        html = """
        <html>
        <body>
            <main>
                <p>Main content here.</p>
            </main>
        </body>
        </html>
        """
        result = extract_html(html, "https://www.eeoc.gov/test")
        assert "Main content here" in result.markdown

    def test_extract_html_selector_miss_falls_back(self):
        """If content_selector doesn't match, should fall back to default chain."""
        from employee_help.scraper.extractors.html import extract_html

        html = """
        <html>
        <body>
            <main>
                <p>Fallback content.</p>
            </main>
        </body>
        </html>
        """
        result = extract_html(html, "https://www.eeoc.gov/test", content_selector="#nonexistent")
        assert "Fallback content" in result.markdown
