"""Tests for Legal Aid at Work source configuration and content category (E.6)."""

from __future__ import annotations

import re

import pytest
import yaml

from employee_help.retrieval.service import CONSUMER_CATEGORIES
from employee_help.storage.models import ContentCategory


# ---------------------------------------------------------------------------
# ContentCategory enum tests
# ---------------------------------------------------------------------------

class TestContentCategory:
    def test_legal_aid_resource_exists(self):
        assert ContentCategory.LEGAL_AID_RESOURCE.value == "legal_aid_resource"

    def test_roundtrip(self):
        cat = ContentCategory("legal_aid_resource")
        assert cat is ContentCategory.LEGAL_AID_RESOURCE

    def test_in_consumer_categories(self):
        assert "legal_aid_resource" in CONSUMER_CATEGORIES


# ---------------------------------------------------------------------------
# Source config tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def config():
    with open("config/sources/legal_aid_at_work.yaml") as f:
        return yaml.safe_load(f)


class TestSourceConfig:
    def test_loads(self, config):
        assert config is not None

    def test_slug(self, config):
        assert config["source"]["slug"] == "legal_aid_at_work"

    def test_source_type(self, config):
        assert config["source"]["source_type"] == "agency"

    def test_seed_urls_present(self, config):
        urls = config["crawl"]["seed_urls"]
        assert len(urls) >= 2

    def test_content_category(self, config):
        assert config["extraction"]["content_category"] == "legal_aid_resource"

    def test_rate_limit_respects_robots(self, config):
        assert config["crawl"]["rate_limit_seconds"] >= 10.0

    def test_max_pages(self, config):
        assert config["crawl"]["max_pages"] >= 123

    def test_chunking_strategy(self, config):
        assert config["chunking"]["strategy"] == "heading_based"


# ---------------------------------------------------------------------------
# URL classification tests
# ---------------------------------------------------------------------------

class TestUrlClassification:
    """Verify allowlist/blocklist patterns match expected URLs."""

    @pytest.fixture(autouse=True)
    def _load_patterns(self, config):
        self.allowlist = [re.compile(p) for p in config["crawl"]["allowlist_patterns"]]
        self.blocklist = [re.compile(p) for p in config["crawl"]["blocklist_patterns"]]

    def _is_allowed(self, url: str) -> bool:
        """URL matches allowlist and is not blocked."""
        allowed = any(p.search(url) for p in self.allowlist)
        blocked = any(p.search(url) for p in self.blocklist)
        return allowed and not blocked

    def test_factsheet_page_allowed(self):
        assert self._is_allowed("https://legalaidatwork.org/factsheet/overtime-pay/")

    def test_factsheet_page_allowed_no_trailing_slash(self):
        assert self._is_allowed("https://legalaidatwork.org/factsheet/overtime-pay")

    def test_factsheet_archive_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/factsheet/")

    def test_facttopic_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/facttopic/discrimination/")

    def test_guides_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/guides/employment-rights/")

    def test_sample_letters_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/sample-letters/demand-letter/")

    def test_spanish_translation_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/es/factsheet/overtime-pay/")

    def test_chinese_translation_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/zh/factsheet/overtime-pay/")

    def test_donate_page_blocked(self):
        assert not self._is_allowed("https://legalaidatwork.org/donate/")

    def test_about_page_not_allowed(self):
        """About page doesn't match allowlist (no /factsheet/ in path)."""
        assert not self._is_allowed("https://legalaidatwork.org/about/")
