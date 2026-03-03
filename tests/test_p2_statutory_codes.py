"""Tests for P2 statutory code configurations (E.3 knowledge expansion).

Verifies Health & Safety Code, Education Code, and Civil Code configs
load correctly and are routed through the PUBINFO pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from employee_help.config import load_source_config


# ── Config Loading Tests ─────────────────────────────────────


class TestHealthSafetyCodeConfig:

    def test_config_loads(self):
        cfg = load_source_config("config/sources/health_safety_code.yaml")
        assert cfg.slug == "health_safety_code"
        assert cfg.source_type.value == "statutory_code"
        assert cfg.enabled is True

    def test_statutory_settings(self):
        cfg = load_source_config("config/sources/health_safety_code.yaml")
        assert cfg.statutory is not None
        assert cfg.statutory.code_abbreviation == "HSC"
        assert cfg.statutory.code_name == "Health & Safety Code"
        assert cfg.statutory.citation_prefix == "Cal. Health & Safety Code"
        assert cfg.statutory.method == "pubinfo"

    def test_targets_division_5(self):
        cfg = load_source_config("config/sources/health_safety_code.yaml")
        assert cfg.statutory.target_divisions == ["5."]

    def test_content_category_is_statutory(self):
        cfg = load_source_config("config/sources/health_safety_code.yaml")
        assert cfg.extraction.content_category == "statutory_code"

    def test_chunking_strategy(self):
        cfg = load_source_config("config/sources/health_safety_code.yaml")
        assert cfg.chunking.strategy == "section_boundary"


class TestEducationCodeConfig:

    def test_config_loads(self):
        cfg = load_source_config("config/sources/education_code.yaml")
        assert cfg.slug == "education_code"
        assert cfg.source_type.value == "statutory_code"
        assert cfg.enabled is True

    def test_statutory_settings(self):
        cfg = load_source_config("config/sources/education_code.yaml")
        assert cfg.statutory is not None
        assert cfg.statutory.code_abbreviation == "EDC"
        assert cfg.statutory.code_name == "Education Code"
        assert cfg.statutory.citation_prefix == "Cal. Educ. Code"
        assert cfg.statutory.method == "pubinfo"

    def test_targets_division_4(self):
        cfg = load_source_config("config/sources/education_code.yaml")
        assert cfg.statutory.target_divisions == ["4."]

    def test_content_category_is_statutory(self):
        cfg = load_source_config("config/sources/education_code.yaml")
        assert cfg.extraction.content_category == "statutory_code"


class TestCivilCodeConfig:

    def test_config_loads(self):
        cfg = load_source_config("config/sources/civil_code.yaml")
        assert cfg.slug == "civil_code"
        assert cfg.source_type.value == "statutory_code"
        assert cfg.enabled is True

    def test_statutory_settings(self):
        cfg = load_source_config("config/sources/civil_code.yaml")
        assert cfg.statutory is not None
        assert cfg.statutory.code_abbreviation == "CIV"
        assert cfg.statutory.code_name == "Civil Code"
        assert cfg.statutory.citation_prefix == "Cal. Civ. Code"
        assert cfg.statutory.method == "pubinfo"

    def test_targets_divisions_1_and_3(self):
        cfg = load_source_config("config/sources/civil_code.yaml")
        assert cfg.statutory.target_divisions == ["1.", "3."]

    def test_content_category_is_statutory(self):
        cfg = load_source_config("config/sources/civil_code.yaml")
        assert cfg.extraction.content_category == "statutory_code"


# ── Cross-Config Tests ───────────────────────────────────────


class TestP2CodesIntegration:

    def test_all_configs_load_without_error(self):
        slugs = ["health_safety_code", "education_code", "civil_code"]
        for slug in slugs:
            cfg = load_source_config(f"config/sources/{slug}.yaml")
            assert cfg.statutory is not None, f"{slug} missing statutory config"
            assert cfg.statutory.method == "pubinfo", f"{slug} should use pubinfo method"

    def test_all_use_pubinfo_method(self):
        slugs = ["health_safety_code", "education_code", "civil_code"]
        for slug in slugs:
            cfg = load_source_config(f"config/sources/{slug}.yaml")
            assert cfg.statutory.method == "pubinfo"

    def test_no_duplicate_slugs_with_existing_configs(self):
        from employee_help.config import load_all_source_configs

        all_configs = load_all_source_configs("config/sources")
        slugs = [c.slug for c in all_configs]
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"

    def test_code_abbreviations_are_unique_per_config(self):
        """Each config should have a unique (code_abbreviation, target_divisions) pair."""
        from employee_help.config import load_all_source_configs

        all_configs = load_all_source_configs("config/sources")
        statutory_configs = [c for c in all_configs if c.statutory is not None]
        keys = [
            (c.statutory.code_abbreviation, tuple(c.statutory.target_divisions))
            for c in statutory_configs
        ]
        assert len(keys) == len(set(keys)), f"Duplicate code+division combos: {keys}"

    def test_citation_prefixes_match_known_prefixes(self):
        """Citation prefixes should match the standard California prefixes."""
        from employee_help.scraper.extractors.statute import CITATION_PREFIXES

        expected = {
            "HSC": "Cal. Health & Safety Code",
            "EDC": "Cal. Educ. Code",
            "CIV": "Cal. Civ. Code",
        }
        for code, prefix in expected.items():
            assert CITATION_PREFIXES.get(code) == prefix, (
                f"{code} citation prefix mismatch: "
                f"expected {prefix!r}, got {CITATION_PREFIXES.get(code)!r}"
            )


# ── PUBINFO Filtering Tests (slow, requires downloaded data) ─


@pytest.mark.slow
class TestP2CodesPubinfo:
    """Integration tests that query the actual PUBINFO database."""

    @pytest.fixture(autouse=True)
    def _require_pubinfo(self):
        pubinfo_dir = Path("data/pubinfo")
        zips = sorted(pubinfo_dir.glob("pubinfo_*.zip"), reverse=True)
        if not zips:
            pytest.skip("PUBINFO data not downloaded")
        self.zip_path = zips[0]

    def test_hsc_division_5_has_sections(self):
        from employee_help.scraper.extractors.pubinfo import PubinfoLoader

        loader = PubinfoLoader(self.zip_path)
        all_sections = loader.parse_law_sections()
        filtered = loader.filter_sections(all_sections, target_codes=["HSC"], target_divisions=["5."])
        assert len(filtered) >= 400

    def test_edc_division_4_has_sections(self):
        from employee_help.scraper.extractors.pubinfo import PubinfoLoader

        loader = PubinfoLoader(self.zip_path)
        all_sections = loader.parse_law_sections()
        filtered = loader.filter_sections(all_sections, target_codes=["EDC"], target_divisions=["4."])
        assert len(filtered) >= 2000

    def test_civ_divisions_1_3_has_sections(self):
        from employee_help.scraper.extractors.pubinfo import PubinfoLoader

        loader = PubinfoLoader(self.zip_path)
        all_sections = loader.parse_law_sections()
        filtered = loader.filter_sections(all_sections, target_codes=["CIV"], target_divisions=["1.", "3."])
        assert len(filtered) >= 2000

    def test_hsc_produces_statute_sections(self):
        from employee_help.scraper.extractors.pubinfo import PubinfoLoader

        loader = PubinfoLoader(self.zip_path)
        all_sections = loader.parse_law_sections()
        filtered = loader.filter_sections(all_sections, target_codes=["HSC"], target_divisions=["5."])
        statute_sections = loader.to_statute_sections(filtered[:10])
        assert len(statute_sections) > 0
        for s in statute_sections:
            assert "Cal. Health & Safety Code" in s.citation
            assert s.text.strip()
