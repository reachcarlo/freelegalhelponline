"""Tests for the source registry — models, storage, config loading, and pipeline integration."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from employee_help.config import (
    ChunkingConfig,
    SourceConfig,
    load_source_config,
    load_all_source_configs,
)
from employee_help.pipeline import classify_content_category
from employee_help.storage.models import (
    ContentCategory,
    ContentType,
    CrawlRun,
    Document,
    Source,
    SourceType,
    UpsertStatus,
)
from employee_help.storage.storage import Storage


# ── Source model tests ────────────────────────────────────────


class TestSourceModel:

    def test_source_defaults(self):
        s = Source(name="CRD", slug="crd", source_type=SourceType.AGENCY, base_url="https://crd.ca.gov")
        assert s.enabled is True
        assert s.id is None
        assert isinstance(s.created_at, datetime)

    def test_source_type_enum(self):
        assert SourceType("agency") == SourceType.AGENCY
        assert SourceType("statutory_code") == SourceType.STATUTORY_CODE

    def test_content_category_enum(self):
        assert ContentCategory("agency_guidance") == ContentCategory.AGENCY_GUIDANCE
        assert ContentCategory("statutory_code") == ContentCategory.STATUTORY_CODE
        assert ContentCategory("fact_sheet") == ContentCategory.FACT_SHEET
        assert ContentCategory("faq") == ContentCategory.FAQ
        assert ContentCategory("poster") == ContentCategory.POSTER
        assert ContentCategory("regulation") == ContentCategory.REGULATION

    def test_document_has_source_fields(self):
        doc = Document(
            source_url="https://example.com",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="test",
            content_hash="abc",
            source_id=1,
            content_category=ContentCategory.FACT_SHEET,
        )
        assert doc.source_id == 1
        assert doc.content_category == ContentCategory.FACT_SHEET

    def test_chunk_has_new_fields(self):
        from employee_help.storage.models import Chunk
        c = Chunk(
            content="test",
            content_hash="abc",
            chunk_index=0,
            heading_path="test",
            token_count=10,
            content_category=ContentCategory.STATUTORY_CODE,
            citation="Cal. Lab. Code § 1102.5",
            is_active=True,
        )
        assert c.content_category == ContentCategory.STATUTORY_CODE
        assert c.citation == "Cal. Lab. Code § 1102.5"
        assert c.is_active is True


# ── Storage source CRUD tests ────────────────────────────────


class TestSourceStorage:

    @pytest.fixture
    def storage(self):
        s = Storage(":memory:")
        yield s
        s.close()

    def test_create_source(self, storage):
        source = Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://calcivilrights.ca.gov",
        )
        created = storage.create_source(source)
        assert created.id is not None
        assert created.id > 0

    def test_get_source_by_slug(self, storage):
        source = Source(
            name="DIR", slug="dir", source_type=SourceType.AGENCY,
            base_url="https://dir.ca.gov",
        )
        storage.create_source(source)
        found = storage.get_source("dir")
        assert found is not None
        assert found.name == "DIR"
        assert found.slug == "dir"
        assert found.source_type == SourceType.AGENCY

    def test_get_source_not_found(self, storage):
        assert storage.get_source("nonexistent") is None

    def test_get_source_by_id(self, storage):
        source = Source(
            name="EDD", slug="edd", source_type=SourceType.AGENCY,
            base_url="https://edd.ca.gov",
        )
        created = storage.create_source(source)
        found = storage.get_source_by_id(created.id)
        assert found is not None
        assert found.slug == "edd"

    def test_get_all_sources(self, storage):
        for name, slug in [("CRD", "crd"), ("DIR", "dir"), ("EDD", "edd")]:
            storage.create_source(Source(
                name=name, slug=slug, source_type=SourceType.AGENCY,
                base_url=f"https://{slug}.ca.gov",
            ))
        all_sources = storage.get_all_sources()
        assert len(all_sources) == 3

    def test_get_all_sources_enabled_only(self, storage):
        storage.create_source(Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov", enabled=True,
        ))
        disabled = Source(
            name="TEST", slug="test", source_type=SourceType.AGENCY,
            base_url="https://test.ca.gov", enabled=False,
        )
        storage.create_source(disabled)
        enabled = storage.get_all_sources(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].slug == "crd"

    def test_update_source(self, storage):
        source = Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov", enabled=True,
        )
        storage.create_source(source)
        source.enabled = False
        source.name = "CRD Updated"
        storage.update_source(source)
        found = storage.get_source("crd")
        assert found.enabled is False
        assert found.name == "CRD Updated"

    def test_create_run_with_source_id(self, storage):
        source = Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov",
        )
        storage.create_source(source)
        run = storage.create_run(source_id=source.id)
        assert run.source_id == source.id

    def test_get_latest_run_by_source(self, storage):
        s1 = storage.create_source(Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov",
        ))
        s2 = storage.create_source(Source(
            name="DIR", slug="dir", source_type=SourceType.AGENCY,
            base_url="https://dir.ca.gov",
        ))
        storage.create_run(source_id=s1.id)
        run2 = storage.create_run(source_id=s2.id)

        latest = storage.get_latest_run(source_id=s2.id)
        assert latest is not None
        assert latest["id"] == run2.id
        assert latest["source_id"] == s2.id

    def test_document_with_source_and_category(self, storage):
        source = storage.create_source(Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov",
        ))
        run = storage.create_run(source_id=source.id)

        doc = Document(
            source_url="https://crd.ca.gov/employment/",
            title="Employment",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="abc123",
            crawl_run_id=run.id,
            source_id=source.id,
            content_category=ContentCategory.AGENCY_GUIDANCE,
        )
        stored, status = storage.upsert_document(doc)
        assert status == UpsertStatus.NEW
        assert stored.source_id == source.id
        assert stored.content_category == ContentCategory.AGENCY_GUIDANCE

        # Retrieve and verify
        retrieved = storage.get_document_by_url("https://crd.ca.gov/employment/")
        assert retrieved.source_id == source.id
        assert retrieved.content_category == ContentCategory.AGENCY_GUIDANCE

    def test_chunks_with_category_and_citation(self, storage):
        from employee_help.storage.models import Chunk

        source = storage.create_source(Source(
            name="Lab Code", slug="labor_code", source_type=SourceType.STATUTORY_CODE,
            base_url="https://leginfo.legislature.ca.gov",
        ))
        run = storage.create_run(source_id=source.id)
        doc = Document(
            source_url="https://leginfo.legislature.ca.gov/1102.5",
            title="Section 1102.5",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="def456",
            crawl_run_id=run.id,
            source_id=source.id,
            content_category=ContentCategory.STATUTORY_CODE,
        )
        stored_doc, _ = storage.upsert_document(doc)

        chunks = [Chunk(
            content="Whistleblower protection text",
            content_hash="chunk1",
            chunk_index=0,
            heading_path="Lab Code > Div 2 > § 1102.5",
            token_count=50,
            document_id=stored_doc.id,
            content_category=ContentCategory.STATUTORY_CODE,
            citation="Cal. Lab. Code § 1102.5",
            is_active=True,
        )]
        storage.insert_chunks(chunks)

        retrieved = storage.get_chunks_for_document(stored_doc.id)
        assert len(retrieved) == 1
        assert retrieved[0].content_category == ContentCategory.STATUTORY_CODE
        assert retrieved[0].citation == "Cal. Lab. Code § 1102.5"
        assert retrieved[0].is_active is True

    def test_get_document_count_by_source(self, storage):
        s1 = storage.create_source(Source(
            name="CRD", slug="crd", source_type=SourceType.AGENCY,
            base_url="https://crd.ca.gov",
        ))
        s2 = storage.create_source(Source(
            name="DIR", slug="dir", source_type=SourceType.AGENCY,
            base_url="https://dir.ca.gov",
        ))
        run = storage.create_run(source_id=s1.id)

        for i in range(3):
            storage.upsert_document(Document(
                source_url=f"https://crd.ca.gov/page{i}",
                title=f"CRD Page {i}",
                content_type=ContentType.HTML,
                raw_content="content",
                content_hash=f"crd{i}",
                crawl_run_id=run.id,
                source_id=s1.id,
            ))

        run2 = storage.create_run(source_id=s2.id)
        storage.upsert_document(Document(
            source_url="https://dir.ca.gov/page0",
            title="DIR Page 0",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="dir0",
            crawl_run_id=run2.id,
            source_id=s2.id,
        ))

        assert storage.get_document_count(source_id=s1.id) == 3
        assert storage.get_document_count(source_id=s2.id) == 1
        assert storage.get_document_count() == 4

    def test_migration_is_idempotent(self, storage):
        """Running migrate() multiple times should not error."""
        storage.migrate()
        storage.migrate()
        storage.migrate()
        # If we get here, migrations are idempotent


# ── Source config loading tests ───────────────────────────────


class TestSourceConfigLoading:

    def _write_source_yaml(self, tmpdir, filename, data):
        path = Path(tmpdir) / filename
        with open(path, "w") as f:
            yaml.dump(data, f)
        return str(path)

    def _minimal_source_data(self, slug="test"):
        return {
            "source": {
                "name": "Test Source",
                "slug": slug,
                "source_type": "agency",
                "base_url": "https://test.ca.gov",
                "enabled": True,
            },
            "crawl": {
                "seed_urls": ["https://test.ca.gov/"],
                "allowlist_patterns": ["test\\.ca\\.gov"],
                "rate_limit_seconds": 1.0,
                "max_pages": 50,
            },
            "database_path": "data/test.db",
        }

    def test_load_source_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", self._minimal_source_data())
            config = load_source_config(path)
            assert config.name == "Test Source"
            assert config.slug == "test"
            assert config.source_type == SourceType.AGENCY
            assert config.base_url == "https://test.ca.gov"
            assert config.enabled is True
            assert len(config.seed_urls) == 1

    def test_load_source_config_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_source_config("/nonexistent/path.yaml")

    def test_load_source_config_missing_name(self):
        data = self._minimal_source_data()
        del data["source"]["name"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            with pytest.raises(ValueError, match="source.name"):
                load_source_config(path)

    def test_load_source_config_missing_slug(self):
        data = self._minimal_source_data()
        del data["source"]["slug"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            with pytest.raises(ValueError, match="source.slug"):
                load_source_config(path)

    def test_load_source_config_invalid_source_type(self):
        data = self._minimal_source_data()
        data["source"]["source_type"] = "invalid_type"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            with pytest.raises(ValueError, match="Invalid source_type"):
                load_source_config(path)

    def test_load_source_config_statutory(self):
        data = self._minimal_source_data()
        data["source"]["source_type"] = "statutory_code"
        data["chunking"] = {"strategy": "section_boundary", "max_tokens": 2000, "overlap_tokens": 0}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            config = load_source_config(path)
            assert config.source_type == SourceType.STATUTORY_CODE
            assert config.chunking.strategy == "section_boundary"
            assert config.chunking.overlap_tokens == 0

    def test_load_source_config_with_extraction(self):
        data = self._minimal_source_data()
        data["extraction"] = {
            "content_selector": "#main-content",
            "boilerplate_patterns": ["Skip to Content", "Back to Top"],
            "content_category": "fact_sheet",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            config = load_source_config(path)
            assert config.extraction.content_selector == "#main-content"
            assert len(config.extraction.boilerplate_patterns) == 2
            assert config.extraction.content_category == "fact_sheet"

    def test_load_source_config_invalid_regex(self):
        data = self._minimal_source_data()
        data["crawl"]["allowlist_patterns"] = ["[invalid"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", data)
            with pytest.raises(ValueError, match="allowlist"):
                load_source_config(path)

    def test_to_crawl_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_source_yaml(tmpdir, "test.yaml", self._minimal_source_data())
            source_config = load_source_config(path)
            crawl_config = source_config.to_crawl_config()
            assert crawl_config.seed_urls == source_config.seed_urls
            assert crawl_config.rate_limit_seconds == source_config.rate_limit_seconds

    def test_load_all_source_configs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_source_yaml(tmpdir, "crd.yaml", self._minimal_source_data("crd"))
            self._write_source_yaml(tmpdir, "dir.yaml", self._minimal_source_data("dir"))
            configs = load_all_source_configs(tmpdir, enabled_only=True)
            assert len(configs) == 2
            slugs = {c.slug for c in configs}
            assert slugs == {"crd", "dir"}

    def test_load_all_source_configs_filters_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_enabled = self._minimal_source_data("crd")
            data_disabled = self._minimal_source_data("test")
            data_disabled["source"]["enabled"] = False
            self._write_source_yaml(tmpdir, "crd.yaml", data_enabled)
            self._write_source_yaml(tmpdir, "test.yaml", data_disabled)
            configs = load_all_source_configs(tmpdir, enabled_only=True)
            assert len(configs) == 1
            assert configs[0].slug == "crd"

    def test_load_all_source_configs_dir_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_all_source_configs("/nonexistent/dir")

    def test_load_crd_source_config(self):
        """Integration test: load the actual CRD source config file."""
        config_path = Path("config/sources/crd.yaml")
        if not config_path.exists():
            pytest.skip("CRD config not found")
        config = load_source_config(config_path)
        assert config.slug == "crd"
        assert config.source_type == SourceType.AGENCY
        assert len(config.seed_urls) >= 1
        assert config.chunking.strategy == "heading_based"


# ── Content categorization tests ──────────────────────────────


class TestContentCategorization:

    def test_leginfo_url_is_statutory(self):
        cat = classify_content_category(
            "https://leginfo.legislature.ca.gov/codes_displaySection.xhtml?lawCode=LAB",
            ContentType.HTML,
        )
        assert cat == ContentCategory.STATUTORY_CODE

    def test_pdf_factsheet_is_fact_sheet(self):
        cat = classify_content_category(
            "https://crd.ca.gov/uploads/Fact-Sheet-Employment.pdf",
            ContentType.PDF,
        )
        assert cat == ContentCategory.FACT_SHEET

    def test_pdf_poster_is_poster(self):
        cat = classify_content_category(
            "https://crd.ca.gov/uploads/Employment-Poster-Notice.pdf",
            ContentType.PDF,
        )
        assert cat == ContentCategory.POSTER

    def test_faq_page_is_faq(self):
        cat = classify_content_category(
            "https://dir.ca.gov/dlse/faq_overview.htm",
            ContentType.HTML,
        )
        assert cat == ContentCategory.FAQ

    def test_generic_html_is_agency_guidance(self):
        cat = classify_content_category(
            "https://crd.ca.gov/employment/protected-categories/",
            ContentType.HTML,
        )
        assert cat == ContentCategory.AGENCY_GUIDANCE

    def test_generic_pdf_is_agency_guidance(self):
        cat = classify_content_category(
            "https://crd.ca.gov/uploads/some-document.pdf",
            ContentType.PDF,
        )
        assert cat == ContentCategory.AGENCY_GUIDANCE


# ── Chunking strategy config tests ────────────────────────────


class TestChunkingConfig:

    def test_default_strategy(self):
        c = ChunkingConfig()
        assert c.strategy == "heading_based"

    def test_section_boundary_strategy(self):
        c = ChunkingConfig(max_tokens=2000, overlap_tokens=0, strategy="section_boundary")
        assert c.strategy == "section_boundary"

    def test_invalid_strategy(self):
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            ChunkingConfig(strategy="invalid")
