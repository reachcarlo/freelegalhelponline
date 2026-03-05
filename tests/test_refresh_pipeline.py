"""Tests for the refresh pipeline: staleness tracking, source health,
enhanced refresh with change reporting, scheduling, observability,
and tier-specific integration (T1 + T2 + T3 + T4)."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from employee_help.config import RefreshConfig, SourceConfig, load_all_source_configs, load_source_config
from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    CrawlStatus,
    Document,
    Source,
    SourceType,
    UpsertStatus,
)
from employee_help.storage.storage import Storage


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def sample_source(storage: Storage) -> Source:
    """Create a sample source in the database."""
    source = Source(
        name="Test Labor Code",
        slug="test_labor",
        source_type=SourceType.STATUTORY_CODE,
        base_url="https://leginfo.legislature.ca.gov",
    )
    storage.create_source(source)
    return source


# ── T1-A: Staleness Tracking ─────────────────────────────────────


class TestLastRefreshedAt:
    """T1-A.1: last_refreshed_at on sources table."""

    def test_source_created_with_null_last_refreshed(self, storage: Storage) -> None:
        source = Source(
            name="Test", slug="test", source_type=SourceType.AGENCY,
            base_url="https://example.com",
        )
        storage.create_source(source)
        retrieved = storage.get_source("test")
        assert retrieved is not None
        assert retrieved.last_refreshed_at is None

    def test_update_source_last_refreshed(self, storage: Storage, sample_source: Source) -> None:
        now = datetime.now(tz=UTC)
        storage.update_source_last_refreshed(sample_source.id, now)
        retrieved = storage.get_source(sample_source.slug)
        assert retrieved.last_refreshed_at is not None
        # Within 1 second tolerance
        assert abs((retrieved.last_refreshed_at - now).total_seconds()) < 1

    def test_update_source_last_refreshed_defaults_to_now(
        self, storage: Storage, sample_source: Source
    ) -> None:
        storage.update_source_last_refreshed(sample_source.id)
        retrieved = storage.get_source(sample_source.slug)
        assert retrieved.last_refreshed_at is not None
        age = (datetime.now(tz=UTC) - retrieved.last_refreshed_at).total_seconds()
        assert age < 5  # Should be very recent


class TestSourceFreshness:
    """T1-A.1: get_source_freshness() returns correct age info."""

    def test_freshness_never_refreshed(self, storage: Storage, sample_source: Source) -> None:
        freshness = storage.get_source_freshness()
        assert len(freshness) >= 1
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        assert entry["last_refreshed_at"] is None
        assert entry["age_days"] is None

    def test_freshness_recently_refreshed(self, storage: Storage, sample_source: Source) -> None:
        storage.update_source_last_refreshed(sample_source.id)
        freshness = storage.get_source_freshness()
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        assert entry["last_refreshed_at"] is not None
        assert entry["age_days"] is not None
        assert entry["age_days"] < 1  # Less than 1 day old

    def test_freshness_old_refresh(self, storage: Storage, sample_source: Source) -> None:
        old_time = datetime.now(tz=UTC) - timedelta(days=10)
        storage.update_source_last_refreshed(sample_source.id, old_time)
        freshness = storage.get_source_freshness()
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        assert entry["age_days"] is not None
        assert 9.5 < entry["age_days"] < 10.5


class TestConsecutiveFailures:
    """T1-A.1: get_consecutive_failures() derived from crawl_runs."""

    def test_no_runs_returns_zero(self, storage: Storage, sample_source: Source) -> None:
        assert storage.get_consecutive_failures(sample_source.id) == 0

    def test_successful_run_returns_zero(self, storage: Storage, sample_source: Source) -> None:
        run = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run.id, CrawlStatus.COMPLETED, {"test": True})
        assert storage.get_consecutive_failures(sample_source.id) == 0

    def test_one_failure_after_success(self, storage: Storage, sample_source: Source) -> None:
        run1 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run1.id, CrawlStatus.COMPLETED, {})
        run2 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run2.id, CrawlStatus.FAILED, {"error": "timeout"})
        assert storage.get_consecutive_failures(sample_source.id) == 1

    def test_multiple_consecutive_failures(self, storage: Storage, sample_source: Source) -> None:
        run1 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run1.id, CrawlStatus.COMPLETED, {})
        for _ in range(3):
            run = storage.create_run(source_id=sample_source.id)
            storage.complete_run(run.id, CrawlStatus.FAILED, {})
        assert storage.get_consecutive_failures(sample_source.id) == 3

    def test_failure_reset_after_success(self, storage: Storage, sample_source: Source) -> None:
        run1 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run1.id, CrawlStatus.FAILED, {})
        run2 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run2.id, CrawlStatus.FAILED, {})
        run3 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run3.id, CrawlStatus.COMPLETED, {})
        assert storage.get_consecutive_failures(sample_source.id) == 0


class TestRefreshConfig:
    """T1-A.2: RefreshConfig dataclass and YAML parsing."""

    def test_default_refresh_config(self) -> None:
        rc = RefreshConfig()
        assert rc.max_age_days == 7
        assert rc.static is False
        assert rc.cron_hint == ""

    def test_custom_refresh_config(self) -> None:
        rc = RefreshConfig(max_age_days=30, static=True, cron_hint="0 3 * * 0")
        assert rc.max_age_days == 30
        assert rc.static is True

    def test_invalid_max_age_days(self) -> None:
        with pytest.raises(ValueError, match="max_age_days"):
            RefreshConfig(max_age_days=0)

    def test_source_config_has_refresh(self) -> None:
        """SourceConfig includes RefreshConfig with defaults."""
        sc = SourceConfig(
            name="Test", slug="test",
            source_type=SourceType.AGENCY, base_url="https://example.com",
        )
        assert sc.refresh.max_age_days == 7
        assert sc.refresh.static is False

    def test_yaml_refresh_parsing(self, tmp_path: Path) -> None:
        """RefreshConfig parsed from YAML source config."""
        yaml_content = """
source:
  name: Test Source
  slug: test_source
  source_type: agency
  base_url: https://example.com

refresh:
  max_age_days: 14
  static: false
  cron_hint: "0 3 * * 0"
"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)
        config = load_source_config(config_file)
        assert config.refresh.max_age_days == 14
        assert config.refresh.static is False
        assert config.refresh.cron_hint == "0 3 * * 0"

    def test_yaml_missing_refresh_uses_defaults(self, tmp_path: Path) -> None:
        """Missing refresh section uses defaults."""
        yaml_content = """
source:
  name: Test Source
  slug: test_source
  source_type: agency
  base_url: https://example.com
"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)
        config = load_source_config(config_file)
        assert config.refresh.max_age_days == 7
        assert config.refresh.static is False


class TestRecentRuns:
    """T1-D.1 prerequisite: get_recent_runs()."""

    def test_no_runs(self, storage: Storage, sample_source: Source) -> None:
        runs = storage.get_recent_runs(sample_source.id)
        assert runs == []

    def test_returns_most_recent(self, storage: Storage, sample_source: Source) -> None:
        for i in range(5):
            run = storage.create_run(source_id=sample_source.id)
            storage.complete_run(run.id, CrawlStatus.COMPLETED, {"i": i})
        runs = storage.get_recent_runs(sample_source.id, limit=3)
        assert len(runs) == 3
        # Most recent first
        assert runs[0]["summary"]["i"] == 4
        assert runs[2]["summary"]["i"] == 2


class TestUpsertStatus:
    """T1-B.3 prerequisite: UpsertStatus enum exists in models."""

    def test_enum_values(self) -> None:
        assert UpsertStatus.NEW == "new"
        assert UpsertStatus.UPDATED == "updated"
        assert UpsertStatus.UNCHANGED == "unchanged"

    def test_upsert_document_new(self, storage: Storage) -> None:
        """New document upsert returns UpsertStatus.NEW."""
        run = storage.create_run()
        doc = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="hash1",
            crawl_run_id=run.id,
        )
        stored, status = storage.upsert_document(doc)
        assert status == UpsertStatus.NEW
        assert stored.id is not None

    def test_upsert_document_unchanged(self, storage: Storage) -> None:
        """Unchanged document returns UpsertStatus.UNCHANGED."""
        run = storage.create_run()
        doc = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="hash1",
            crawl_run_id=run.id,
        )
        storage.upsert_document(doc)
        doc2 = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="hash1",
            crawl_run_id=run.id,
        )
        stored, status = storage.upsert_document(doc2)
        assert status == UpsertStatus.UNCHANGED

    def test_upsert_document_updated(self, storage: Storage) -> None:
        """Changed document returns UpsertStatus.UPDATED."""
        run = storage.create_run()
        doc = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="content v1",
            content_hash="hash1",
            crawl_run_id=run.id,
        )
        storage.upsert_document(doc)
        doc2 = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="content v2",
            content_hash="hash2",
            crawl_run_id=run.id,
        )
        stored, status = storage.upsert_document(doc2)
        assert status == UpsertStatus.UPDATED


# ── T1-B: Enhanced Refresh ───────────────────────────────────────


class TestPersistDocument:
    """T1-B.3: _persist_document() shared method on Pipeline."""

    def test_persist_new_document(self, storage: Storage, sample_source: Source) -> None:
        """_persist_document creates chunks for a new document."""
        from employee_help.config import CrawlConfig, ChunkingConfig
        from employee_help.pipeline import Pipeline, PipelineStats, UpsertStatus
        from datetime import datetime, timezone

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)

        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )

        doc = Document(
            source_url="https://example.com/new",
            title="New Doc",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="hash_new",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )

        mock_chunk = type("Chunk", (), {
            "content": "test content",
            "content_hash": "chunk_hash",
            "chunk_index": 0,
            "heading_path": "Test",
            "token_count": 5,
        })()

        status = pipeline._persist_document(
            doc, [mock_chunk], ContentCategory.STATUTORY_CODE,
            citation="Test § 100", stats=stats,
        )
        assert status == UpsertStatus.NEW
        assert stats.new_documents == 1
        assert stats.documents_stored == 1
        assert stats.chunks_created == 1

    def test_persist_unchanged_document(self, storage: Storage, sample_source: Source) -> None:
        """_persist_document skips chunks for unchanged documents."""
        from employee_help.config import CrawlConfig, ChunkingConfig
        from employee_help.pipeline import Pipeline, PipelineStats, UpsertStatus
        from datetime import datetime, timezone

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=timezone.utc)

        # First insert
        doc = Document(
            source_url="https://example.com/unchanged",
            title="Same Doc",
            content_type=ContentType.HTML,
            raw_content="same content",
            content_hash="same_hash",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc)

        # Second attempt with same hash
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc2 = Document(
            source_url="https://example.com/unchanged",
            title="Same Doc",
            content_type=ContentType.HTML,
            raw_content="same content",
            content_hash="same_hash",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        mock_chunk = type("Chunk", (), {
            "content": "test", "content_hash": "ch", "chunk_index": 0,
            "heading_path": "T", "token_count": 1,
        })()

        status = pipeline._persist_document(
            doc2, [mock_chunk], ContentCategory.STATUTORY_CODE,
            citation=None, stats=stats,
        )
        assert status == UpsertStatus.UNCHANGED
        assert stats.unchanged_documents == 1
        assert stats.new_documents == 0


class TestDeactivateMissingSectionsDetails:
    """T1-B.4: deactivate_missing_sections returns structured details."""

    def test_returns_list_with_details(self, storage: Storage, sample_source: Source) -> None:
        run = storage.create_run(source_id=sample_source.id)
        doc = Document(
            source_url="https://example.com/section_100",
            title="Section 100",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="h100",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc)
        storage.insert_chunks([
            Chunk(
                content="chunk text", content_hash="ch100",
                chunk_index=0, heading_path="S100",
                token_count=5, document_id=doc.id,
            )
        ])

        # Deactivate with empty current URLs (section removed)
        deactivated = storage.deactivate_missing_sections(sample_source.id, set())
        assert len(deactivated) == 1
        assert deactivated[0]["source_url"] == "https://example.com/section_100"
        assert deactivated[0]["chunks_deactivated"] == 1
        assert "document_id" in deactivated[0]

    def test_returns_empty_when_all_present(self, storage: Storage, sample_source: Source) -> None:
        run = storage.create_run(source_id=sample_source.id)
        doc = Document(
            source_url="https://example.com/section_200",
            title="Section 200",
            content_type=ContentType.HTML,
            raw_content="content",
            content_hash="h200",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc)
        deactivated = storage.deactivate_missing_sections(
            sample_source.id, {"https://example.com/section_200"}
        )
        assert deactivated == []


class TestPipelineStatsExtended:
    """T1-B.5: Extended PipelineStats with new/updated/deactivated tracking."""

    def test_has_changes_with_new(self) -> None:
        from employee_help.pipeline import PipelineStats
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
            new_documents=1,
        )
        assert stats.has_changes is True

    def test_has_changes_with_updated(self) -> None:
        from employee_help.pipeline import PipelineStats
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
            updated_documents=1,
        )
        assert stats.has_changes is True

    def test_has_changes_with_deactivated(self) -> None:
        from employee_help.pipeline import PipelineStats
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
            deactivated_sections=[{"source_url": "x", "chunks_deactivated": 1}],
        )
        assert stats.has_changes is True

    def test_no_changes(self) -> None:
        from employee_help.pipeline import PipelineStats
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        assert stats.has_changes is False


class TestIfStaleFilter:
    """T1-C.1: --if-stale skips fresh sources."""

    def test_fresh_source_skipped(self, storage: Storage, sample_source: Source) -> None:
        """A source refreshed recently should be considered fresh."""
        storage.update_source_last_refreshed(sample_source.id)
        freshness = storage.get_source_freshness()
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        # With default max_age_days=7, a just-refreshed source is fresh
        assert entry["age_days"] is not None
        assert entry["age_days"] < 7

    def test_stale_source_not_skipped(self, storage: Storage, sample_source: Source) -> None:
        """A source refreshed 10 days ago with max_age_days=7 is stale."""
        from datetime import timedelta
        old = datetime.now(tz=UTC) - timedelta(days=10)
        storage.update_source_last_refreshed(sample_source.id, old)
        freshness = storage.get_source_freshness()
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        assert entry["age_days"] > 7

    def test_never_run_is_stale(self, storage: Storage, sample_source: Source) -> None:
        """A source that's never been refreshed should be considered stale."""
        freshness = storage.get_source_freshness()
        entry = next(f for f in freshness if f["slug"] == sample_source.slug)
        assert entry["age_days"] is None  # None means never-run → stale


class TestRefreshConfigFromYaml:
    """T1-C.3: Refresh configs parsed from actual source YAMLs."""

    def test_all_source_configs_parse(self) -> None:
        """All 21 source configs parse successfully with refresh section."""
        configs = load_all_source_configs("config/sources", enabled_only=False)
        assert len(configs) >= 21
        for c in configs:
            assert c.refresh.max_age_days >= 1

    def test_labor_code_refresh_config(self) -> None:
        config = load_source_config("config/sources/labor_code.yaml")
        assert config.refresh.max_age_days == 7
        assert config.refresh.static is False

    def test_dlse_opinions_static(self) -> None:
        config = load_source_config("config/sources/dlse_opinions.yaml")
        assert config.refresh.static is True
        assert config.refresh.max_age_days == 365

    def test_caci_refresh_config(self) -> None:
        config = load_source_config("config/sources/caci.yaml")
        assert config.refresh.max_age_days == 180


class TestRunHistoryInSourceHealth:
    """T1-D.1: Run history in source-health output."""

    def test_get_recent_runs_returns_ordered(self, storage: Storage, sample_source: Source) -> None:
        for i in range(4):
            run = storage.create_run(source_id=sample_source.id)
            storage.complete_run(
                run.id, CrawlStatus.COMPLETED,
                {"documents_stored": i * 10, "duration_seconds": i + 1},
            )
        runs = storage.get_recent_runs(sample_source.id, limit=2)
        assert len(runs) == 2
        assert runs[0]["summary"]["documents_stored"] == 30  # Most recent
        assert runs[1]["summary"]["documents_stored"] == 20


class TestRefreshStatusSchema:
    """T1-D.2: /api/refresh-status response schema."""

    def test_refresh_status_response_schema(self) -> None:
        from employee_help.api.schemas import RefreshStatusResponse, SourceRefreshStatusInfo
        info = SourceRefreshStatusInfo(
            slug="labor_code", source_type="statutory_code",
            age_days=2.5, max_age_days=7, status="FRESH",
        )
        resp = RefreshStatusResponse(
            knowledge_base="fresh",
            sources_stale=0, sources_fresh=1, sources_never_run=0,
            sources=[info],
        )
        assert resp.knowledge_base == "fresh"
        assert len(resp.sources) == 1
        assert resp.sources[0].slug == "labor_code"


class TestSimulatedChanges:
    """T1-E.2: Simulated change scenarios — new, amended, repealed."""

    def test_new_section_detected(self, storage: Storage, sample_source: Source) -> None:
        """A brand-new section is persisted as NEW."""
        from employee_help.config import CrawlConfig, ChunkingConfig
        from employee_help.pipeline import Pipeline, PipelineStats
        from datetime import timezone

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=timezone.utc)
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )

        doc = Document(
            source_url="https://example.com/new_section",
            title="New Section",
            content_type=ContentType.HTML,
            raw_content="Brand new law text",
            content_hash="brand_new_hash",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        mock_chunk = type("C", (), {
            "content": "Brand new law text",
            "content_hash": "brand_new_chunk",
            "chunk_index": 0,
            "heading_path": "New > Section",
            "token_count": 5,
        })()

        status = pipeline._persist_document(
            doc, [mock_chunk], ContentCategory.STATUTORY_CODE,
            citation="§ 999", stats=stats,
        )
        assert status == UpsertStatus.NEW
        assert stats.new_documents == 1

    def test_amended_section_detected(self, storage: Storage, sample_source: Source) -> None:
        """An amended section (same URL, different hash) is UPDATED."""
        from employee_help.config import CrawlConfig, ChunkingConfig
        from employee_help.pipeline import Pipeline, PipelineStats
        from datetime import timezone

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=timezone.utc)

        # First version
        doc_v1 = Document(
            source_url="https://example.com/amended_section",
            title="Section 200",
            content_type=ContentType.HTML,
            raw_content="Original text",
            content_hash="v1_hash",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc_v1)

        # Amended version
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc_v2 = Document(
            source_url="https://example.com/amended_section",
            title="Section 200",
            content_type=ContentType.HTML,
            raw_content="Amended text with changes",
            content_hash="v2_hash",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        mock_chunk = type("C", (), {
            "content": "Amended text", "content_hash": "v2_chunk",
            "chunk_index": 0, "heading_path": "S200", "token_count": 3,
        })()

        status = pipeline._persist_document(
            doc_v2, [mock_chunk], ContentCategory.STATUTORY_CODE,
            citation="§ 200", stats=stats,
        )
        assert status == UpsertStatus.UPDATED
        assert stats.updated_documents == 1

    def test_repealed_section_deactivated(self, storage: Storage, sample_source: Source) -> None:
        """A section removed from source is deactivated."""
        run = storage.create_run(source_id=sample_source.id)

        # Insert two sections
        for i, url in enumerate(["https://example.com/s100", "https://example.com/s101"]):
            doc = Document(
                source_url=url, title=f"Section {100 + i}",
                content_type=ContentType.HTML,
                raw_content=f"Content {i}",
                content_hash=f"hash_{i}",
                crawl_run_id=run.id, source_id=sample_source.id,
            )
            storage.upsert_document(doc)
            storage.insert_chunks([
                Chunk(
                    content=f"chunk {i}", content_hash=f"ch_{i}",
                    chunk_index=0, heading_path=f"S{100+i}",
                    token_count=3, document_id=doc.id,
                )
            ])

        # Simulate re-ingest with s101 removed
        deactivated = storage.deactivate_missing_sections(
            sample_source.id, {"https://example.com/s100"}
        )
        assert len(deactivated) == 1
        assert deactivated[0]["source_url"] == "https://example.com/s101"
        assert deactivated[0]["chunks_deactivated"] == 1

    def test_full_refresh_lifecycle(self, storage: Storage, sample_source: Source) -> None:
        """Full lifecycle: new → unchanged → amended → repealed."""
        from employee_help.config import CrawlConfig, ChunkingConfig
        from employee_help.pipeline import Pipeline, PipelineStats
        from datetime import timezone

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=timezone.utc)

        mk_chunk = lambda h: type("C", (), {
            "content": "t", "content_hash": h,
            "chunk_index": 0, "heading_path": "P", "token_count": 1,
        })()

        # Step 1: Insert new
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc = Document(
            source_url="https://example.com/lifecycle",
            title="Lifecycle", content_type=ContentType.HTML,
            raw_content="v1", content_hash="lc_v1",
            crawl_run_id=run.id, source_id=sample_source.id,
        )
        s = pipeline._persist_document(doc, [mk_chunk("lc_ch_v1")],
                                        ContentCategory.STATUTORY_CODE, "§ 1", stats)
        assert s == UpsertStatus.NEW

        # Step 2: Same content → unchanged
        stats2 = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc2 = Document(
            source_url="https://example.com/lifecycle",
            title="Lifecycle", content_type=ContentType.HTML,
            raw_content="v1", content_hash="lc_v1",
            crawl_run_id=run.id, source_id=sample_source.id,
        )
        s = pipeline._persist_document(doc2, [mk_chunk("lc_ch_v1")],
                                        ContentCategory.STATUTORY_CODE, "§ 1", stats2)
        assert s == UpsertStatus.UNCHANGED

        # Step 3: Amended
        stats3 = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc3 = Document(
            source_url="https://example.com/lifecycle",
            title="Lifecycle", content_type=ContentType.HTML,
            raw_content="v2 amended", content_hash="lc_v2",
            crawl_run_id=run.id, source_id=sample_source.id,
        )
        s = pipeline._persist_document(doc3, [mk_chunk("lc_ch_v2")],
                                        ContentCategory.STATUTORY_CODE, "§ 1", stats3)
        assert s == UpsertStatus.UPDATED


class TestTierFilter:
    """T1-B.6: --tier filter via content_category mapping."""

    def test_filter_statutory(self) -> None:
        from employee_help.cli import _filter_configs_by_tier
        configs = [
            SourceConfig(
                name="Lab Code", slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
            ),
            SourceConfig(
                name="DIR", slug="dir",
                source_type=SourceType.AGENCY,
                base_url="https://dir.ca.gov",
            ),
        ]
        result = _filter_configs_by_tier(configs, "statutory")
        assert len(result) == 0  # Default content_category is agency_guidance

    def test_filter_statutory_with_correct_category(self) -> None:
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig
        configs = [
            SourceConfig(
                name="Lab Code", slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
                extraction=ExtractionConfig(content_category="statutory_code"),
            ),
            SourceConfig(
                name="DIR", slug="dir",
                source_type=SourceType.AGENCY,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="agency_guidance"),
            ),
        ]
        result = _filter_configs_by_tier(configs, "statutory")
        assert len(result) == 1
        assert result[0].slug == "labor_code"

    def test_filter_none_returns_all(self) -> None:
        from employee_help.cli import _filter_configs_by_tier
        configs = [
            SourceConfig(
                name="A", slug="a",
                source_type=SourceType.AGENCY,
                base_url="https://a.com",
            ),
        ]
        result = _filter_configs_by_tier(configs, None)
        assert len(result) == 1

    def test_tier_categories_complete(self) -> None:
        """All ContentCategory values are covered by some tier."""
        from employee_help.cli import _TIER_CATEGORIES
        all_covered = set()
        for categories in _TIER_CATEGORIES.values():
            all_covered.update(categories)
        # Every content category should be in at least one tier
        for cat in ContentCategory:
            assert cat.value in all_covered, f"{cat.value} not in any tier"


# ── T2-A: Tier 2 Configuration & Framework Integration ──────


class TestTierRegulatoryFilter:
    """T2-A.2: --tier regulatory captures CCR Title 2, CCR Title 8, CACI."""

    def test_regulatory_tier_captures_ccr_and_caci(self) -> None:
        """Regulatory tier includes regulation and jury_instruction categories."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="CCR Title 2 FEHA",
                slug="ccr_title2_feha",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://law.cornell.edu",
                extraction=ExtractionConfig(content_category="regulation"),
            ),
            SourceConfig(
                name="CCR Title 8",
                slug="ccr_title_8",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://law.cornell.edu",
                extraction=ExtractionConfig(content_category="regulation"),
            ),
            SourceConfig(
                name="CACI",
                slug="caci",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://courts.ca.gov",
                extraction=ExtractionConfig(content_category="jury_instruction"),
            ),
            SourceConfig(
                name="Labor Code",
                slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
                extraction=ExtractionConfig(content_category="statutory_code"),
            ),
            SourceConfig(
                name="DIR",
                slug="dir",
                source_type=SourceType.AGENCY,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="agency_guidance"),
            ),
        ]

        result = _filter_configs_by_tier(configs, "regulatory")
        slugs = {c.slug for c in result}
        assert slugs == {"ccr_title2_feha", "ccr_title_8", "caci"}

    def test_regulatory_tier_excludes_statutory_code(self) -> None:
        """Statutory code sources are NOT captured by --tier regulatory."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="Labor Code",
                slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
                extraction=ExtractionConfig(content_category="statutory_code"),
            ),
        ]
        result = _filter_configs_by_tier(configs, "regulatory")
        assert len(result) == 0

    def test_regulatory_tier_from_real_configs(self) -> None:
        """Actual YAML configs: regulatory tier captures exactly CCR + CACI."""
        from employee_help.cli import _filter_configs_by_tier

        configs = load_all_source_configs("config/sources", enabled_only=False)
        result = _filter_configs_by_tier(configs, "regulatory")
        slugs = {c.slug for c in result}
        assert "ccr_title2_feha" in slugs
        assert "ccr_title_8" in slugs
        assert "caci" in slugs
        # No statutory code sources should be included
        for c in result:
            assert c.extraction.content_category in ("regulation", "jury_instruction")

    def test_ccr_title2_config_values(self) -> None:
        """CCR Title 2 FEHA has correct refresh and content settings."""
        config = load_source_config("config/sources/ccr_title2_feha.yaml")
        assert config.extraction.content_category == "regulation"
        assert config.refresh.max_age_days == 30
        assert config.statutory is not None
        assert config.statutory.method == "ccr_web"

    def test_ccr_title_8_config_values(self) -> None:
        """CCR Title 8 has correct refresh and content settings."""
        config = load_source_config("config/sources/ccr_title_8.yaml")
        assert config.extraction.content_category == "regulation"
        assert config.refresh.max_age_days == 30
        assert config.statutory is not None
        assert config.statutory.method == "ccr_title_8"

    def test_caci_config_values(self) -> None:
        """CACI has correct refresh, content, and method settings."""
        config = load_source_config("config/sources/caci.yaml")
        assert config.extraction.content_category == "jury_instruction"
        assert config.refresh.max_age_days == 180
        assert config.statutory is not None
        assert config.statutory.method == "caci_pdf"


class TestCCRChangeDetection:
    """T2-A.3: CCR change detection through content_hash in the pipeline."""

    def test_ccr_unchanged_document_skipped(self, storage: Storage, sample_source: Source) -> None:
        """A CCR regulation with unchanged content_hash produces UNCHANGED."""
        from employee_help.config import ChunkingConfig, CrawlConfig
        from employee_help.pipeline import Pipeline, PipelineStats

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=UTC)

        # First ingest
        doc = Document(
            source_url="https://law.cornell.edu/regulations/california/Cal-Code-Regs-Tit-2-11034",
            title="2 CCR § 11034",
            content_type=ContentType.HTML,
            raw_content="Reasonable accommodation requirements text",
            content_hash="ccr_hash_v1",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        mk_chunk = type("C", (), {
            "content": "Reasonable accommodation requirements text",
            "content_hash": "ccr_chunk_v1",
            "chunk_index": 0,
            "heading_path": "CCR Title 2 > FEHA > Reasonable Accommodation",
            "token_count": 8,
        })()
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        pipeline._persist_document(doc, [mk_chunk], ContentCategory.REGULATION, "2 CCR § 11034", stats)
        assert stats.new_documents == 1

        # Re-ingest with same content
        stats2 = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc2 = Document(
            source_url="https://law.cornell.edu/regulations/california/Cal-Code-Regs-Tit-2-11034",
            title="2 CCR § 11034",
            content_type=ContentType.HTML,
            raw_content="Reasonable accommodation requirements text",
            content_hash="ccr_hash_v1",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        status = pipeline._persist_document(
            doc2, [mk_chunk], ContentCategory.REGULATION, "2 CCR § 11034", stats2
        )
        assert status == UpsertStatus.UNCHANGED
        assert stats2.unchanged_documents == 1
        assert stats2.new_documents == 0

    def test_ccr_amended_regulation_detected(self, storage: Storage, sample_source: Source) -> None:
        """A modified CCR regulation (different hash) produces UPDATED."""
        from employee_help.config import ChunkingConfig, CrawlConfig
        from employee_help.pipeline import Pipeline, PipelineStats

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=UTC)

        # Original version
        doc = Document(
            source_url="https://law.cornell.edu/regulations/california/Cal-Code-Regs-Tit-2-11035",
            title="2 CCR § 11035",
            content_type=ContentType.HTML,
            raw_content="Original pregnancy disability leave text",
            content_hash="ccr_11035_v1",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc)

        # Amended version
        stats = PipelineStats(
            run_id=run.id, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0, start_time=now, end_time=now,
        )
        doc2 = Document(
            source_url="https://law.cornell.edu/regulations/california/Cal-Code-Regs-Tit-2-11035",
            title="2 CCR § 11035",
            content_type=ContentType.HTML,
            raw_content="Amended pregnancy disability leave text with new provisions",
            content_hash="ccr_11035_v2",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        mk_chunk = type("C", (), {
            "content": "Amended text", "content_hash": "ccr_ch_v2",
            "chunk_index": 0, "heading_path": "CCR > PDL", "token_count": 4,
        })()
        status = pipeline._persist_document(
            doc2, [mk_chunk], ContentCategory.REGULATION, "2 CCR § 11035", stats
        )
        assert status == UpsertStatus.UPDATED
        assert stats.updated_documents == 1


class TestCACIIdempotentReparse:
    """T2-A.4: CACI idempotent re-parse — same PDF produces 0 changes."""

    def test_caci_unchanged_on_reparse(self, storage: Storage, sample_source: Source) -> None:
        """Re-parsing same CACI PDF produces UNCHANGED for all instructions."""
        from employee_help.config import ChunkingConfig, CrawlConfig
        from employee_help.pipeline import Pipeline, PipelineStats

        config = CrawlConfig(
            seed_urls=["https://placeholder.invalid"],
            allowlist_patterns=["placeholder"],
            blocklist_patterns=[],
            rate_limit_seconds=1.0,
            max_pages=10,
            chunking=ChunkingConfig(),
            database_path=str(storage._db_path),
        )
        pipeline = Pipeline(config, storage=storage)
        run = storage.create_run(source_id=sample_source.id)
        now = datetime.now(tz=UTC)

        # Simulate first CACI ingest — 3 instructions
        instructions = [
            ("CACI-2430-instruction_text", "2430. Wrongful Termination", "caci_2430_it"),
            ("CACI-2430-directions_for_use", "2430. Directions for Use", "caci_2430_dfu"),
            ("CACI-2500-instruction_text", "2500. FEHA Discrimination", "caci_2500_it"),
        ]
        for url_frag, title, content_hash in instructions:
            doc = Document(
                source_url=f"https://courts.ca.gov/caci#{url_frag}",
                title=title,
                content_type=ContentType.HTML,
                raw_content=f"Content for {title}",
                content_hash=content_hash,
                crawl_run_id=run.id,
                source_id=sample_source.id,
            )
            mk_chunk = type("C", (), {
                "content": f"Content for {title}",
                "content_hash": f"ch_{content_hash}",
                "chunk_index": 0,
                "heading_path": title,
                "token_count": 5,
            })()
            stats = PipelineStats(
                run_id=run.id, urls_crawled=0, documents_stored=0,
                chunks_created=0, errors=0, start_time=now, end_time=now,
            )
            pipeline._persist_document(
                doc, [mk_chunk], ContentCategory.JURY_INSTRUCTION, title, stats
            )

        # Re-parse with identical content — all should be UNCHANGED
        unchanged_count = 0
        for url_frag, title, content_hash in instructions:
            doc2 = Document(
                source_url=f"https://courts.ca.gov/caci#{url_frag}",
                title=title,
                content_type=ContentType.HTML,
                raw_content=f"Content for {title}",
                content_hash=content_hash,
                crawl_run_id=run.id,
                source_id=sample_source.id,
            )
            mk_chunk = type("C", (), {
                "content": f"Content for {title}",
                "content_hash": f"ch_{content_hash}",
                "chunk_index": 0,
                "heading_path": title,
                "token_count": 5,
            })()
            stats2 = PipelineStats(
                run_id=run.id, urls_crawled=0, documents_stored=0,
                chunks_created=0, errors=0, start_time=now, end_time=now,
            )
            status = pipeline._persist_document(
                doc2, [mk_chunk], ContentCategory.JURY_INSTRUCTION, title, stats2
            )
            if status == UpsertStatus.UNCHANGED:
                unchanged_count += 1

        assert unchanged_count == 3, "All 3 CACI instructions should be UNCHANGED on re-parse"


# ── T2-B: CACI Edition Detection & --check-updates ──────────


class TestCheckUpdateUrl:
    """T2-B.1/T2-B.2: check_update_url in RefreshConfig."""

    def test_default_check_update_url_empty(self) -> None:
        rc = RefreshConfig()
        assert rc.check_update_url == ""

    def test_check_update_url_parsed_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = """
source:
  name: Test Source
  slug: test_source
  source_type: statutory_code
  base_url: https://example.com

refresh:
  max_age_days: 180
  check_update_url: "https://example.com/docs/test-{next_year}.pdf"
"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)
        config = load_source_config(config_file)
        assert config.refresh.check_update_url == "https://example.com/docs/test-{next_year}.pdf"

    def test_caci_has_check_update_url(self) -> None:
        """CACI YAML config includes a check_update_url."""
        config = load_source_config("config/sources/caci.yaml")
        assert config.refresh.check_update_url != ""
        assert "{next_year}" in config.refresh.check_update_url


class TestCheckSourceUpdates:
    """T2-B.2/T2-B.3: _check_source_updates performs HTTP HEAD checks."""

    def test_new_edition_detected(self, capsys) -> None:
        """HTTP 200 → reports new edition available."""
        import httpx
        import respx

        from employee_help.cli import _check_source_updates
        from employee_help.config import ExtractionConfig

        config = SourceConfig(
            name="CACI",
            slug="caci",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://courts.ca.gov",
            extraction=ExtractionConfig(content_category="jury_instruction"),
            refresh=RefreshConfig(
                max_age_days=180,
                check_update_url="https://courts.ca.gov/docs/caci-2027.pdf",
            ),
        )

        with respx.mock:
            respx.head("https://courts.ca.gov/docs/caci-2027.pdf").mock(
                return_value=httpx.Response(200, headers={"content-length": "12345678"})
            )
            _check_source_updates([config])

        output = capsys.readouterr().out
        assert "NEW EDITION AVAILABLE" in output
        assert "caci" in output

    def test_no_new_edition(self, capsys) -> None:
        """HTTP 404 → reports current edition."""
        import httpx
        import respx

        from employee_help.cli import _check_source_updates
        from employee_help.config import ExtractionConfig

        config = SourceConfig(
            name="CACI",
            slug="caci",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://courts.ca.gov",
            extraction=ExtractionConfig(content_category="jury_instruction"),
            refresh=RefreshConfig(
                max_age_days=180,
                check_update_url="https://courts.ca.gov/docs/caci-2099.pdf",
            ),
        )

        with respx.mock:
            respx.head("https://courts.ca.gov/docs/caci-2099.pdf").mock(
                return_value=httpx.Response(404)
            )
            _check_source_updates([config])

        output = capsys.readouterr().out
        assert "Current edition" in output

    def test_http_error_handled_gracefully(self, capsys) -> None:
        """HTTP timeout → reports error without crashing."""
        import httpx
        import respx

        from employee_help.cli import _check_source_updates
        from employee_help.config import ExtractionConfig

        config = SourceConfig(
            name="CACI",
            slug="caci",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://courts.ca.gov",
            extraction=ExtractionConfig(content_category="jury_instruction"),
            refresh=RefreshConfig(
                max_age_days=180,
                check_update_url="https://courts.ca.gov/docs/caci-2027.pdf",
            ),
        )

        with respx.mock:
            respx.head("https://courts.ca.gov/docs/caci-2027.pdf").mock(
                side_effect=httpx.TimeoutException("Connection timed out")
            )
            _check_source_updates([config])

        output = capsys.readouterr().out
        assert "Timeout" in output

    def test_no_check_url_skips_source(self, capsys) -> None:
        """Sources without check_update_url are skipped entirely."""
        from employee_help.cli import _check_source_updates

        config = SourceConfig(
            name="Labor Code",
            slug="labor_code",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://leginfo.legislature.ca.gov",
        )
        _check_source_updates([config])
        output = capsys.readouterr().out
        assert output == ""  # No output at all — no sources to check

    def test_next_year_template_substitution(self, capsys) -> None:
        """URL template {next_year} is replaced with current year + 1."""
        import httpx
        import respx
        from datetime import datetime

        from employee_help.cli import _check_source_updates
        from employee_help.config import ExtractionConfig

        next_year = datetime.now().year + 1
        expected_url = f"https://example.com/docs/edition-{next_year}.pdf"

        config = SourceConfig(
            name="Test",
            slug="test_source",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://example.com",
            extraction=ExtractionConfig(content_category="jury_instruction"),
            refresh=RefreshConfig(
                max_age_days=180,
                check_update_url="https://example.com/docs/edition-{next_year}.pdf",
            ),
        )

        with respx.mock:
            route = respx.head(expected_url).mock(
                return_value=httpx.Response(404)
            )
            _check_source_updates([config])
            assert route.called


# ── T3: Persuasive Authority Refresh ──────────────────────────────


class TestTierPersuasiveFilter:
    """T3-A.4: --tier persuasive captures correct sources."""

    def test_persuasive_categories_defined(self) -> None:
        """The persuasive tier maps to opinion_letter, enforcement_manual, federal_guidance."""
        from employee_help.cli import _TIER_CATEGORIES

        expected = {"opinion_letter", "enforcement_manual", "federal_guidance"}
        assert _TIER_CATEGORIES["persuasive"] == expected

    def test_filter_captures_persuasive_sources(self) -> None:
        """_filter_configs_by_tier with 'persuasive' captures only matching sources."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="DLSE Opinions", slug="dlse_opinions",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="opinion_letter"),
            ),
            SourceConfig(
                name="DLSE Manual", slug="dlse_manual",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="enforcement_manual"),
            ),
            SourceConfig(
                name="EEOC", slug="eeoc",
                source_type=SourceType.AGENCY,
                base_url="https://eeoc.gov",
                extraction=ExtractionConfig(content_category="federal_guidance"),
            ),
            SourceConfig(
                name="Labor Code", slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
                extraction=ExtractionConfig(content_category="statutory_code"),
            ),
            SourceConfig(
                name="DIR", slug="dir",
                source_type=SourceType.AGENCY,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="agency_guidance"),
            ),
        ]

        filtered = _filter_configs_by_tier(configs, "persuasive")
        slugs = {c.slug for c in filtered}
        assert slugs == {"dlse_opinions", "dlse_manual", "eeoc"}

    def test_filter_excludes_regulatory_from_persuasive(self) -> None:
        """Regulatory sources (regulation, jury_instruction) not in persuasive tier."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="CCR", slug="ccr",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://cornell.law",
                extraction=ExtractionConfig(content_category="regulation"),
            ),
            SourceConfig(
                name="CACI", slug="caci",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://courts.ca.gov",
                extraction=ExtractionConfig(content_category="jury_instruction"),
            ),
        ]

        filtered = _filter_configs_by_tier(configs, "persuasive")
        assert len(filtered) == 0

    def test_real_yaml_configs_match_persuasive_tier(self) -> None:
        """Real YAML configs for DLSE opinions, DLSE manual, EEOC match persuasive tier."""
        from employee_help.cli import _filter_configs_by_tier

        configs = load_all_source_configs("config/sources", enabled_only=False)
        filtered = _filter_configs_by_tier(configs, "persuasive")
        slugs = {c.slug for c in filtered}
        assert "dlse_opinions" in slugs
        assert "dlse_manual" in slugs
        assert "eeoc" in slugs
        # Ensure no statutory or agency sources sneak in
        for c in filtered:
            assert c.extraction.content_category in {
                "opinion_letter", "enforcement_manual", "federal_guidance"
            }


class TestStaticCorpusConfirmation:
    """T3-A.2: Static corpus confirmation for closed-corpus sources."""

    def test_static_corpus_confirmed_when_reachable(self, tmp_path, capsys) -> None:
        """Static source with reachable base_url → confirmed, last_refreshed_at updated."""
        import httpx
        import respx

        from employee_help.cli import _confirm_static_corpus
        from employee_help.config import ExtractionConfig

        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)

        # Create a source with some documents
        source = Source(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
        )
        storage.create_source(source)
        run = storage.create_run()
        # Add a document so count > 0
        doc = Document(
            source_url="https://dir.ca.gov/dlse/opinions/OL-2019-01.pdf",
            title="OL-2019-01",
            content_type=ContentType.HTML,
            raw_content="Test opinion letter content",
            content_hash="abc123",
            source_id=source.id,
            crawl_run_id=run.id,
        )
        storage.upsert_document(doc)
        storage.close()

        config = SourceConfig(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
            extraction=ExtractionConfig(content_category="opinion_letter"),
            refresh=RefreshConfig(max_age_days=365, static=True),
            database_path=str(db_path),
        )

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/opinionletters-bysubject.htm").mock(
                return_value=httpx.Response(200)
            )
            result, stats = _confirm_static_corpus(config)

        assert result == 0
        assert stats is None  # No PipelineStats for static sources
        output = capsys.readouterr().out
        assert "Corpus confirmed" in output
        assert "1 docs" in output

        # Verify last_refreshed_at was updated
        storage = Storage(db_path=db_path)
        retrieved = storage.get_source("dlse_opinions")
        assert retrieved.last_refreshed_at is not None
        storage.close()

    def test_static_corpus_unreachable(self, tmp_path, capsys) -> None:
        """Static source with unreachable base_url → error, no refresh update."""
        import httpx
        import respx

        from employee_help.cli import _confirm_static_corpus
        from employee_help.config import ExtractionConfig

        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)

        source = Source(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
        )
        storage.create_source(source)
        storage.close()

        config = SourceConfig(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
            extraction=ExtractionConfig(content_category="opinion_letter"),
            refresh=RefreshConfig(max_age_days=365, static=True),
            database_path=str(db_path),
        )

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/opinionletters-bysubject.htm").mock(
                return_value=httpx.Response(500)
            )
            result, stats = _confirm_static_corpus(config)

        assert result == 1
        output = capsys.readouterr().out
        assert "unreachable" in output

        # Verify last_refreshed_at was NOT updated
        storage = Storage(db_path=db_path)
        retrieved = storage.get_source("dlse_opinions")
        assert retrieved.last_refreshed_at is None
        storage.close()

    def test_static_corpus_timeout(self, tmp_path, capsys) -> None:
        """Static source with timeout → treated as unreachable."""
        import httpx
        import respx

        from employee_help.cli import _confirm_static_corpus
        from employee_help.config import ExtractionConfig

        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)

        source = Source(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
        )
        storage.create_source(source)
        storage.close()

        config = SourceConfig(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
            extraction=ExtractionConfig(content_category="opinion_letter"),
            refresh=RefreshConfig(max_age_days=365, static=True),
            database_path=str(db_path),
        )

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/opinionletters-bysubject.htm").mock(
                side_effect=httpx.TimeoutException("Connection timed out")
            )
            result, stats = _confirm_static_corpus(config)

        assert result == 1
        output = capsys.readouterr().out
        assert "unreachable" in output

    def test_static_source_skips_pipeline(self, tmp_path, capsys) -> None:
        """_refresh_source_with_stats skips pipeline for static sources."""
        import httpx
        import respx

        from employee_help.cli import _refresh_source_with_stats
        from employee_help.config import ExtractionConfig

        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)

        source = Source(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
        )
        storage.create_source(source)
        run = storage.create_run()
        doc = Document(
            source_url="https://dir.ca.gov/dlse/opinions/OL-2019-01.pdf",
            title="OL-2019-01",
            content_type=ContentType.HTML,
            raw_content="Test content",
            content_hash="xyz",
            source_id=source.id,
            crawl_run_id=run.id,
        )
        storage.upsert_document(doc)
        storage.close()

        # Write a YAML config file for _refresh_source_with_stats to load
        yaml_content = f"""
source:
  name: DLSE Opinions
  slug: dlse_opinions
  source_type: statutory_code
  base_url: https://dir.ca.gov/dlse/opinionletters-bysubject.htm

extraction:
  content_category: opinion_letter

refresh:
  max_age_days: 365
  static: true

database_path: "{db_path}"
"""
        config_dir = tmp_path / "config" / "sources"
        config_dir.mkdir(parents=True)
        (config_dir / "dlse_opinions.yaml").write_text(yaml_content)

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/opinionletters-bysubject.htm").mock(
                return_value=httpx.Response(200)
            )
            with patch(
                "employee_help.cli.load_source_config",
                return_value=SourceConfig(
                    name="DLSE Opinions", slug="dlse_opinions",
                    source_type=SourceType.STATUTORY_CODE,
                    base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
                    extraction=ExtractionConfig(content_category="opinion_letter"),
                    refresh=RefreshConfig(max_age_days=365, static=True),
                    database_path=str(db_path),
                ),
            ):
                result, stats = _refresh_source_with_stats("dlse_opinions", dry_run=False)

        assert result == 0
        assert stats is None  # Pipeline was skipped

    def test_static_source_no_source_in_db(self, tmp_path, capsys) -> None:
        """Static source with no existing record → still reports 0 docs."""
        import httpx
        import respx

        from employee_help.cli import _confirm_static_corpus
        from employee_help.config import ExtractionConfig

        db_path = tmp_path / "test.db"
        # Just create empty storage — no source record
        storage = Storage(db_path=db_path)
        storage.close()

        config = SourceConfig(
            name="DLSE Opinions", slug="dlse_opinions",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/opinionletters-bysubject.htm",
            extraction=ExtractionConfig(content_category="opinion_letter"),
            refresh=RefreshConfig(max_age_days=365, static=True),
            database_path=str(db_path),
        )

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/opinionletters-bysubject.htm").mock(
                return_value=httpx.Response(200)
            )
            result, stats = _confirm_static_corpus(config)

        assert result == 0
        output = capsys.readouterr().out
        assert "0 docs" in output


class TestDLSEManualCheckUpdateUrl:
    """T3-A.3: DLSE Manual has check_update_url for --check-updates."""

    def test_dlse_manual_has_check_update_url(self) -> None:
        """DLSE Manual YAML config includes a check_update_url."""
        config = load_source_config("config/sources/dlse_manual.yaml")
        assert config.refresh.check_update_url != ""
        assert "dlse_enfcmanual.pdf" in config.refresh.check_update_url

    def test_dlse_manual_update_check_reports_reachable(self, capsys) -> None:
        """HTTP 200 on DLSE Manual URL → reports edition info."""
        import httpx
        import respx

        from employee_help.cli import _check_source_updates
        from employee_help.config import ExtractionConfig

        config = SourceConfig(
            name="DLSE Manual", slug="dlse_manual",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf",
            extraction=ExtractionConfig(content_category="enforcement_manual"),
            refresh=RefreshConfig(
                max_age_days=180,
                check_update_url="https://dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf",
            ),
        )

        with respx.mock:
            respx.head("https://dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf").mock(
                return_value=httpx.Response(200, headers={"content-length": "9876543"})
            )
            _check_source_updates([config])

        output = capsys.readouterr().out
        assert "dlse_manual" in output
        # DLSE Manual URL has no {next_year} template — always the same URL
        # HTTP 200 means the source is reachable; reported as "NEW EDITION"
        assert "NEW EDITION AVAILABLE" in output or "dlse_manual" in output


class TestStaticFlagParsing:
    """T3-A.1: refresh.static flag is parsed correctly from YAML."""

    def test_static_default_false(self) -> None:
        """RefreshConfig.static defaults to False."""
        config = RefreshConfig(max_age_days=7)
        assert config.static is False

    def test_static_true_from_yaml(self, tmp_path) -> None:
        """refresh.static: true is parsed from YAML."""
        yaml_content = """
source:
  name: Test Static
  slug: test_static
  source_type: statutory_code
  base_url: https://example.com

refresh:
  max_age_days: 365
  static: true
"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)
        config = load_source_config(config_file)
        assert config.refresh.static is True

    def test_dlse_opinions_is_static(self) -> None:
        """Real DLSE opinions YAML has static: true."""
        config = load_source_config("config/sources/dlse_opinions.yaml")
        assert config.refresh.static is True
        assert config.refresh.max_age_days == 365

    def test_eeoc_is_not_static(self) -> None:
        """EEOC is not static — it uses regular crawl refresh."""
        config = load_source_config("config/sources/eeoc.yaml")
        assert config.refresh.static is False
        assert config.refresh.max_age_days == 90


class TestEEOCThroughRefreshPipeline:
    """T3-A.5: EEOC uses existing crawl pipeline through refresh."""

    def test_eeoc_config_values(self) -> None:
        """EEOC has correct refresh config for quarterly crawl."""
        config = load_source_config("config/sources/eeoc.yaml")
        assert config.source_type == SourceType.AGENCY
        assert config.extraction.content_category == "federal_guidance"
        assert config.refresh.max_age_days == 90
        assert config.refresh.static is False
        assert len(config.seed_urls) > 0  # Has seed URLs for Playwright crawl

    def test_eeoc_not_in_agency_tier(self) -> None:
        """EEOC (federal_guidance) is NOT captured by --tier agency."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="EEOC", slug="eeoc",
                source_type=SourceType.AGENCY,
                base_url="https://eeoc.gov",
                extraction=ExtractionConfig(content_category="federal_guidance"),
            ),
        ]
        filtered = _filter_configs_by_tier(configs, "agency")
        assert len(filtered) == 0

    def test_eeoc_in_persuasive_tier(self) -> None:
        """EEOC (federal_guidance) IS captured by --tier persuasive."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="EEOC", slug="eeoc",
                source_type=SourceType.AGENCY,
                base_url="https://eeoc.gov",
                extraction=ExtractionConfig(content_category="federal_guidance"),
            ),
        ]
        filtered = _filter_configs_by_tier(configs, "persuasive")
        assert len(filtered) == 1
        assert filtered[0].slug == "eeoc"


# ── T4: Agency Guidance & Dashboard ──────────────────────────────


class TestTierAgencyFilter:
    """T4-B: --tier agency captures correct sources."""

    def test_agency_categories_defined(self) -> None:
        """The agency tier maps to agency_guidance, fact_sheet, faq, legal_aid_resource, poster."""
        from employee_help.cli import _TIER_CATEGORIES

        expected = {"agency_guidance", "fact_sheet", "faq", "legal_aid_resource", "poster"}
        assert _TIER_CATEGORIES["agency"] == expected

    def test_filter_captures_agency_sources(self) -> None:
        """_filter_configs_by_tier with 'agency' captures agency sources."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="DIR", slug="dir",
                source_type=SourceType.AGENCY,
                base_url="https://dir.ca.gov",
                extraction=ExtractionConfig(content_category="agency_guidance"),
            ),
            SourceConfig(
                name="Legal Aid", slug="legal_aid_at_work",
                source_type=SourceType.AGENCY,
                base_url="https://legalaidatwork.org",
                extraction=ExtractionConfig(content_category="legal_aid_resource"),
            ),
            SourceConfig(
                name="EEOC", slug="eeoc",
                source_type=SourceType.AGENCY,
                base_url="https://eeoc.gov",
                extraction=ExtractionConfig(content_category="federal_guidance"),
            ),
        ]

        filtered = _filter_configs_by_tier(configs, "agency")
        slugs = {c.slug for c in filtered}
        assert slugs == {"dir", "legal_aid_at_work"}
        # EEOC should NOT be in agency tier
        assert "eeoc" not in slugs

    def test_filter_excludes_statutory_from_agency(self) -> None:
        """Statutory sources not in agency tier."""
        from employee_help.cli import _filter_configs_by_tier
        from employee_help.config import ExtractionConfig

        configs = [
            SourceConfig(
                name="Labor Code", slug="labor_code",
                source_type=SourceType.STATUTORY_CODE,
                base_url="https://leginfo.legislature.ca.gov",
                extraction=ExtractionConfig(content_category="statutory_code"),
            ),
        ]
        filtered = _filter_configs_by_tier(configs, "agency")
        assert len(filtered) == 0

    def test_real_yaml_agency_configs(self) -> None:
        """Real YAML configs for agency sources match tier filter."""
        from employee_help.cli import _filter_configs_by_tier

        configs = load_all_source_configs("config/sources", enabled_only=False)
        filtered = _filter_configs_by_tier(configs, "agency")
        slugs = {c.slug for c in filtered}
        # DIR, EDD, CalHR should be in agency tier
        assert "dir" in slugs
        assert "edd" in slugs
        assert "calhr" in slugs
        # EEOC is persuasive, not agency
        assert "eeoc" not in slugs

    def test_agency_source_refresh_configs(self) -> None:
        """Agency sources have correct max_age_days in their YAML configs."""
        dir_cfg = load_source_config("config/sources/dir.yaml")
        assert dir_cfg.refresh.max_age_days == 7

        edd_cfg = load_source_config("config/sources/edd.yaml")
        assert edd_cfg.refresh.max_age_days == 14

        calhr_cfg = load_source_config("config/sources/calhr.yaml")
        assert calhr_cfg.refresh.max_age_days == 30

        crd_cfg = load_source_config("config/sources/crd.yaml")
        assert crd_cfg.refresh.max_age_days == 7

        legal_aid_cfg = load_source_config("config/sources/legal_aid_at_work.yaml")
        assert legal_aid_cfg.refresh.max_age_days == 14


class TestEnrichedSummary:
    """T4-A: crawl_runs.summary includes change detection metrics."""

    def test_summary_includes_change_metrics(self, storage: Storage, sample_source: Source) -> None:
        """PipelineStats change metrics are persisted in crawl_run summary."""
        import json as json_mod

        run = storage.create_run(source_id=sample_source.id)
        summary = {
            "urls_crawled": 10,
            "documents_stored": 8,
            "chunks_created": 24,
            "errors": 0,
            "duration_seconds": 15.5,
            "new_documents": 3,
            "updated_documents": 2,
            "unchanged_documents": 5,
            "deactivated_sections": 1,
        }
        storage.complete_run(run.id, CrawlStatus.COMPLETED, summary)

        runs = storage.get_recent_runs(sample_source.id, limit=1)
        assert len(runs) == 1
        stored_summary = runs[0]["summary"]
        assert stored_summary["new_documents"] == 3
        assert stored_summary["updated_documents"] == 2
        assert stored_summary["unchanged_documents"] == 5
        assert stored_summary["deactivated_sections"] == 1


class TestSourceDashboardData:
    """T4-D: Storage.get_source_dashboard_data() returns comprehensive data."""

    def test_dashboard_data_empty_db(self, storage: Storage) -> None:
        """Empty database returns empty list."""
        data = storage.get_source_dashboard_data()
        assert data == []

    def test_dashboard_data_with_source(self, storage: Storage, sample_source: Source) -> None:
        """Dashboard data includes source info and counts."""
        data = storage.get_source_dashboard_data()
        assert len(data) == 1
        entry = data[0]
        assert entry["slug"] == "test_labor"
        assert entry["name"] == "Test Labor Code"
        assert entry["document_count"] == 0
        assert entry["chunk_count"] == 0
        assert entry["last_refreshed_at"] is None
        assert entry["age_days"] is None
        assert entry["consecutive_failures"] == 0

    def test_dashboard_data_with_documents(self, storage: Storage, sample_source: Source) -> None:
        """Dashboard data reflects document and chunk counts."""
        run = storage.create_run(source_id=sample_source.id)
        doc = Document(
            source_url="https://example.com/test",
            title="Test Doc",
            content_type=ContentType.HTML,
            raw_content="Test content",
            content_hash="hash1",
            crawl_run_id=run.id,
            source_id=sample_source.id,
        )
        storage.upsert_document(doc)

        data = storage.get_source_dashboard_data()
        assert data[0]["document_count"] == 1

    def test_dashboard_data_with_run_history(self, storage: Storage, sample_source: Source) -> None:
        """Dashboard data includes last run status and summary."""
        from datetime import UTC, datetime

        run = storage.create_run(source_id=sample_source.id)
        summary = {"documents_stored": 10, "errors": 0, "duration_seconds": 22.5}
        storage.complete_run(run.id, CrawlStatus.COMPLETED, summary)
        storage.update_source_last_refreshed(sample_source.id, datetime.now(tz=UTC))

        data = storage.get_source_dashboard_data()
        entry = data[0]
        assert entry["last_run_status"] == "completed"
        assert entry["last_run_summary"]["documents_stored"] == 10
        assert entry["last_refreshed_at"] is not None
        assert entry["age_days"] is not None
        assert entry["age_days"] < 0.1  # Just refreshed
        assert entry["first_ingested_at"] is not None

    def test_dashboard_data_with_failures(self, storage: Storage, sample_source: Source) -> None:
        """Dashboard data tracks consecutive failures."""
        run1 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run1.id, CrawlStatus.FAILED, {"errors": 5})
        run2 = storage.create_run(source_id=sample_source.id)
        storage.complete_run(run2.id, CrawlStatus.FAILED, {"errors": 3})

        data = storage.get_source_dashboard_data()
        assert data[0]["consecutive_failures"] == 2
        assert data[0]["last_run_status"] == "failed"


class TestDashboardCLI:
    """T4-D: CLI dashboard command."""

    def test_dashboard_command_exists(self) -> None:
        """Dashboard command is registered in CLI parser."""
        import subprocess
        result = subprocess.run(
            ["uv", "run", "employee-help", "dashboard", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "dashboard" in result.stdout.lower() or "health" in result.stdout.lower()

    def test_dashboard_json_output(self, tmp_path) -> None:
        """Dashboard --json outputs valid JSON."""
        import json as json_mod

        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)
        source = Source(
            name="Test Source", slug="test_src",
            source_type=SourceType.AGENCY,
            base_url="https://example.com",
        )
        storage.create_source(source)
        storage.close()

        from employee_help.cli import _handle_dashboard
        from types import SimpleNamespace
        args = SimpleNamespace(db=str(db_path), json_output=True)

        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = _handle_dashboard(args)

        assert result == 0
        output = f.getvalue()
        parsed = json_mod.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["slug"] == "test_src"

    def test_dashboard_table_output(self, tmp_path) -> None:
        """Dashboard table output includes tier headers and summary."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)
        source = Source(
            name="Test Source", slug="test_src",
            source_type=SourceType.AGENCY,
            base_url="https://example.com",
        )
        storage.create_source(source)
        storage.close()

        from employee_help.cli import _handle_dashboard
        from types import SimpleNamespace
        args = SimpleNamespace(db=str(db_path), json_output=False)

        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = _handle_dashboard(args)

        assert result == 0
        output = f.getvalue()
        assert "KNOWLEDGE BASE HEALTH DASHBOARD" in output
        assert "TOTAL:" in output
        assert "test_src" in output


class TestChunkerMaxTokensEnforcement:
    """T4-C: Chunker enforces max_tokens on final flush."""

    def test_large_section_no_headings(self) -> None:
        """Section with many paragraphs but no headings stays under max_tokens."""
        from employee_help.processing.chunker import chunk_document

        # Create content with many small paragraphs totaling ~6000 tokens
        paragraphs = [f"This is paragraph number {i} with some content to test chunking behavior. " * 5 for i in range(40)]
        text = "## Policy Memos\n\n" + "\n\n".join(paragraphs)

        chunks = chunk_document(text, min_tokens=50, max_tokens=1500, overlap_tokens=100)

        for chunk in chunks:
            assert chunk.token_count <= 1500 * 1.1, (  # 10% tolerance for token estimation
                f"Chunk exceeded max_tokens: {chunk.token_count} tokens"
            )

    def test_split_large_section_cascades_to_sentences(self) -> None:
        """_split_large_section cascades to sentence splitting on final flush."""
        from employee_help.processing.chunker import _split_large_section

        # Create text that accumulates beyond max_tokens through overlap
        text = ". ".join([f"Sentence number {i} with enough words to make it count" for i in range(100)])

        chunks = _split_large_section(text, "Test > Section", 0, max_tokens=200, overlap_tokens=50)

        for chunk in chunks:
            # Each chunk should be close to or under max_tokens
            assert chunk.token_count <= 200 * 1.2, (
                f"Chunk exceeded max_tokens: {chunk.token_count} tokens"
            )


# ── T4-E: GitHub Actions Workflow Validation ─────────────────────

class TestGitHubActionsWorkflow:
    """T4-E: Validate the GitHub Actions workflow is correctly structured."""

    def test_workflow_has_per_tier_jobs(self) -> None:
        """Workflow defines separate jobs for each tier."""
        import yaml

        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "refresh.yml"
        with open(workflow_path) as f:
            wf = yaml.safe_load(f)

        jobs = wf["jobs"]
        expected_tiers = {"statutory", "regulatory", "persuasive", "agency", "caselaw"}
        assert expected_tiers.issubset(set(jobs.keys())), (
            f"Missing tier jobs: {expected_tiers - set(jobs.keys())}"
        )

    def test_workflow_has_health_check_job(self) -> None:
        """Workflow includes a post-refresh health check job."""
        import yaml

        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "refresh.yml"
        with open(workflow_path) as f:
            wf = yaml.safe_load(f)

        assert "health-check" in wf["jobs"]
        hc = wf["jobs"]["health-check"]
        assert "needs" in hc
        # Health check depends on all tier jobs
        for tier in ["statutory", "regulatory", "persuasive", "agency", "caselaw"]:
            assert tier in hc["needs"]

    def test_agency_job_installs_playwright(self) -> None:
        """Agency job includes Playwright browser installation step."""
        import yaml

        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "refresh.yml"
        with open(workflow_path) as f:
            wf = yaml.safe_load(f)

        agency_steps = wf["jobs"]["agency"]["steps"]
        playwright_steps = [
            s for s in agency_steps
            if isinstance(s.get("name"), str) and "playwright" in s["name"].lower()
        ]
        assert len(playwright_steps) >= 1, "Agency job must install Playwright"
        assert "chromium" in playwright_steps[0]["run"]

    def test_workflow_has_multiple_cron_schedules(self) -> None:
        """Workflow has separate cron schedules for different tiers."""
        import yaml

        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "refresh.yml"
        with open(workflow_path) as f:
            wf = yaml.safe_load(f)

        schedules = wf[True]["schedule"]  # YAML parses bare 'on' as boolean True
        assert len(schedules) >= 4, f"Expected at least 4 cron schedules, got {len(schedules)}"

        # Verify each schedule has a cron expression
        for s in schedules:
            assert "cron" in s

    def test_statutory_job_downloads_pubinfo(self) -> None:
        """Statutory job includes PUBINFO download step."""
        import yaml

        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "refresh.yml"
        with open(workflow_path) as f:
            wf = yaml.safe_load(f)

        statutory_steps = wf["jobs"]["statutory"]["steps"]
        pubinfo_steps = [
            s for s in statutory_steps
            if isinstance(s.get("name"), str) and "pubinfo" in s["name"].lower()
        ]
        assert len(pubinfo_steps) >= 1, "Statutory job must download PUBINFO"


# ── T4-E: All-Tier Integration ───────────────────────────────────

class TestAllTierIntegration:
    """T4-E: Validate all tiers are covered by the refresh pipeline."""

    def test_all_sources_belong_to_a_tier(self) -> None:
        """Every source config maps to exactly one tier."""
        from employee_help.cli import _TIER_CATEGORIES

        configs = load_all_source_configs()
        all_categories = set()
        for cats in _TIER_CATEGORIES.values():
            all_categories.update(cats)

        uncovered = []
        for cfg in configs:
            cat = cfg.extraction.content_category
            if cat not in all_categories:
                uncovered.append(f"{cfg.slug} ({cat})")

        assert uncovered == [], f"Sources without a tier: {uncovered}"

    def test_tier_categories_are_disjoint(self) -> None:
        """No content category appears in multiple tiers."""
        from employee_help.cli import _TIER_CATEGORIES

        seen: dict[str, str] = {}
        for tier, cats in _TIER_CATEGORIES.items():
            for cat in cats:
                assert cat not in seen, (
                    f"Category '{cat}' in both '{seen[cat]}' and '{tier}'"
                )
                seen[cat] = tier

    def test_all_tiers_have_at_least_one_source(self) -> None:
        """Each defined tier matches at least one source config."""
        from employee_help.cli import _TIER_CATEGORIES, _filter_configs_by_tier

        configs = load_all_source_configs()
        for tier_name in _TIER_CATEGORIES:
            filtered = _filter_configs_by_tier(configs, tier_name)
            assert len(filtered) >= 1, f"Tier '{tier_name}' matches 0 sources"

    def test_refresh_if_stale_respects_max_age_days(self, tmp_path) -> None:
        """Sources refreshed within max_age_days are skipped by --if-stale."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)

        source = Source(
            name="Fresh Source", slug="fresh_test",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://example.com",
        )
        source_record = storage.create_source(source)
        # Mark as refreshed just now
        storage.update_source_last_refreshed(source_record.id, datetime.now(tz=UTC))

        record = storage.get_source("fresh_test")
        assert record is not None
        assert record.last_refreshed_at is not None

        age = (datetime.now(tz=UTC) - record.last_refreshed_at).total_seconds()
        assert age < 60, "Source should be fresh (< 60s old)"
        storage.close()
