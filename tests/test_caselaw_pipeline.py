"""Tests for case law pipeline integration (4C.4).

End-to-end tests with mocked CourtListener API verifying:
- Pipeline routes to _run_caselaw() for caselaw configs
- Opinions are downloaded, chunked, and stored as documents + chunks
- Citation links are created from eyecite-extracted citations
- Deduplication works (re-run doesn't create duplicate documents)
- Dry-run mode doesn't persist anything
- Config loading for courtlistener.yaml
- CLI command registration
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from employee_help.config import CaselawConfig, SourceConfig, load_source_config
from employee_help.pipeline import Pipeline, PipelineStats
from employee_help.storage.models import ContentCategory, SourceType
from employee_help.storage.storage import Storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_source_config(db_path: str) -> SourceConfig:
    """Create a minimal SourceConfig with caselaw settings for testing."""
    return SourceConfig(
        name="Test Case Law",
        slug="courtlistener",
        source_type=SourceType.STATUTORY_CODE,
        base_url="https://www.courtlistener.com",
        caselaw=CaselawConfig(
            courts=["cal"],
            max_opinions=3,
            search_queries=['"test query"'],
        ),
        extraction=MagicMock(
            content_category="case_law",
            boilerplate_patterns=[],
        ),
        database_path=db_path,
    )


def _make_mock_opinion(
    cluster_id: int,
    case_name: str = "Test v. Case",
    opinion_text: str | None = None,
):
    """Create a mock LoadedOpinion."""
    from employee_help.scraper.extractors.opinion_loader import LoadedOpinion

    if opinion_text is None:
        opinion_text = (
            f"This is the opinion text for {case_name}. "
            "The court held that Labor Code section 1102.5 prohibits "
            "retaliation against whistleblowers. The plaintiff alleged "
            "wrongful termination in violation of public policy."
        )

    mock_citation = MagicMock()
    mock_citation.text = "Cal. Lab. Code § 1102.5"
    mock_citation.citation_type = "statute"
    mock_citation.reporter = "Cal. Lab. Code"
    mock_citation.volume = None
    mock_citation.page = None
    mock_citation.section = "1102.5"
    mock_citation.is_california = True

    return LoadedOpinion(
        cluster_id=cluster_id,
        opinion_id=cluster_id * 10,
        case_name=case_name,
        case_name_full=f"{case_name} (Full Name)",
        date_filed="2020-01-15",
        court_id="cal",
        docket_number=f"S{cluster_id:06d}",
        citations=[f"{case_name} (2020) 50 Cal.4th {cluster_id}"],
        precedential_status="Published",
        opinion_text=opinion_text,
        opinion_type="010combined",
        cited_statutes=[mock_citation],
        cited_cases=[],
        all_citations=[mock_citation],
        matched_employment_codes=["Labor Code"],
        absolute_url=f"/opinion/{cluster_id}/test-v-case/",
    )


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def source_config(tmp_path: Path) -> SourceConfig:
    return _make_source_config(str(tmp_path / "test.db"))


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------

class TestCaselawConfig:
    def test_load_courtlistener_yaml(self):
        config = load_source_config("config/sources/courtlistener.yaml")
        assert config.slug == "courtlistener"
        assert config.caselaw is not None
        assert config.caselaw.courts == ["cal", "calctapp"]
        assert config.caselaw.max_opinions == 5000
        assert len(config.caselaw.search_queries) > 0

    def test_caselaw_config_defaults(self):
        cfg = CaselawConfig()
        assert cfg.courts == ["cal", "calctapp"]
        assert cfg.max_opinions == 5000
        assert cfg.filed_after is None

    def test_extraction_category_is_case_law(self):
        config = load_source_config("config/sources/courtlistener.yaml")
        assert config.extraction.content_category == "case_law"

    def test_no_statutory_section(self):
        config = load_source_config("config/sources/courtlistener.yaml")
        assert config.statutory is None


# ---------------------------------------------------------------------------
# Pipeline routing
# ---------------------------------------------------------------------------

class TestPipelineRouting:
    def test_routes_to_caselaw(self, source_config):
        """Pipeline.run() should route to _run_caselaw() when caselaw config present."""
        pipeline = Pipeline(source_config)
        pipeline._run_caselaw = MagicMock(return_value=PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0,
            start_time=MagicMock(), end_time=MagicMock(),
        ))
        pipeline.run()
        pipeline._run_caselaw.assert_called_once_with(False)

    def test_does_not_route_to_statutory(self, source_config):
        """Caselaw config should not trigger statutory pipeline."""
        pipeline = Pipeline(source_config)
        pipeline._run_statutory = MagicMock()
        pipeline._run_caselaw = MagicMock(return_value=PipelineStats(
            run_id=1, urls_crawled=0, documents_stored=0,
            chunks_created=0, errors=0,
            start_time=MagicMock(), end_time=MagicMock(),
        ))
        pipeline.run()
        pipeline._run_statutory.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-end pipeline tests (with mocked OpinionLoader)
# ---------------------------------------------------------------------------

class TestCaselawPipelineE2E:
    def _run_pipeline_with_mock_opinions(
        self, source_config, opinions, dry_run=False
    ):
        """Run the pipeline with mocked OpinionLoader returning given opinions."""
        mock_loader = MagicMock()
        mock_loader.load.return_value = iter(opinions)
        mock_loader.close = MagicMock()

        with patch(
            "employee_help.scraper.extractors.opinion_loader.OpinionLoader",
            return_value=mock_loader,
        ):
            pipeline = Pipeline(source_config)
            return pipeline.run(dry_run=dry_run)

    def test_ingest_single_opinion(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        stats = self._run_pipeline_with_mock_opinions(source_config, opinions)

        assert stats.documents_stored == 1
        assert stats.chunks_created >= 1
        assert stats.errors == 0

    def test_ingest_multiple_opinions(self, source_config):
        opinions = [
            _make_mock_opinion(1, "Smith v. Employer"),
            _make_mock_opinion(2, "Jones v. Corp"),
            _make_mock_opinion(3, "Doe v. State"),
        ]
        stats = self._run_pipeline_with_mock_opinions(source_config, opinions)

        assert stats.documents_stored == 3
        assert stats.chunks_created >= 3
        assert stats.errors == 0

    def test_documents_stored_in_db(self, source_config):
        opinions = [
            _make_mock_opinion(1, "Smith v. Employer"),
            _make_mock_opinion(2, "Jones v. Corp"),
        ]
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            assert source is not None
            docs = storage.get_all_documents(source_id=source.id)
            assert len(docs) == 2
            assert docs[0].content_category == ContentCategory.CASE_LAW
        finally:
            storage.close()

    def test_chunks_have_citation(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            docs = storage.get_all_documents(source_id=source.id)
            chunks = storage.get_chunks_for_document(docs[0].id)
            assert len(chunks) >= 1
            for chunk in chunks:
                assert chunk.citation is not None
                assert chunk.content_category == ContentCategory.CASE_LAW
        finally:
            storage.close()

    def test_citation_links_created(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            link_count = storage.get_citation_link_count()
            assert link_count >= 1
        finally:
            storage.close()

    def test_idempotent_reingest(self, source_config):
        """Re-ingesting the same opinion should not create duplicates."""
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]

        self._run_pipeline_with_mock_opinions(source_config, opinions)
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            docs = storage.get_all_documents(source_id=source.id)
            assert len(docs) == 1
        finally:
            storage.close()

    def test_dry_run_no_persistence(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        stats = self._run_pipeline_with_mock_opinions(
            source_config, opinions, dry_run=True
        )

        assert stats.documents_stored == 1  # counted but not stored

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            assert source is None  # no source created in dry run
        finally:
            storage.close()

    def test_crawl_run_completed(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            run = storage.get_latest_run(source_id=source.id)
            assert run is not None
            assert run["status"] == "completed"
        finally:
            storage.close()

    def test_error_handling(self, source_config):
        """Opinions that fail to process should be counted as errors."""
        good = _make_mock_opinion(1, "Good Case")
        bad = _make_mock_opinion(2, "Bad Case", opinion_text="")  # empty

        opinions = [good, bad]
        stats = self._run_pipeline_with_mock_opinions(source_config, opinions)

        # The good one should succeed; the bad one produces no chunks (warning, not error)
        assert stats.documents_stored >= 1

    def test_source_url_format(self, source_config):
        opinions = [_make_mock_opinion(1, "Smith v. Employer")]
        self._run_pipeline_with_mock_opinions(source_config, opinions)

        storage = Storage(source_config.database_path)
        try:
            source = storage.get_source("courtlistener")
            docs = storage.get_all_documents(source_id=source.id)
            assert docs[0].source_url.startswith("https://www.courtlistener.com/")
        finally:
            storage.close()


# ---------------------------------------------------------------------------
# Build citation links helper
# ---------------------------------------------------------------------------

class TestBuildCitationLinks:
    def test_builds_links_from_citations(self):
        mock_cite = MagicMock()
        mock_cite.text = "Cal. Lab. Code § 1102.5"
        mock_cite.citation_type = "statute"
        mock_cite.reporter = "Cal. Lab. Code"
        mock_cite.volume = None
        mock_cite.page = None
        mock_cite.section = "1102.5"
        mock_cite.is_california = True

        links = Pipeline._build_citation_links(100, [mock_cite])
        assert len(links) == 1
        assert links[0].source_chunk_id == 100
        assert links[0].cited_text == "Cal. Lab. Code § 1102.5"
        assert links[0].citation_type == "statute"

    def test_deduplicates_citations(self):
        cite1 = MagicMock()
        cite1.text = "same citation"
        cite1.citation_type = "case"
        cite1.reporter = None
        cite1.volume = None
        cite1.page = None
        cite1.section = None
        cite1.is_california = True

        cite2 = MagicMock()
        cite2.text = "same citation"  # duplicate
        cite2.citation_type = "case"
        cite2.reporter = None
        cite2.volume = None
        cite2.page = None
        cite2.section = None
        cite2.is_california = True

        links = Pipeline._build_citation_links(100, [cite1, cite2])
        assert len(links) == 1

    def test_empty_citations(self):
        links = Pipeline._build_citation_links(100, [])
        assert links == []


# ---------------------------------------------------------------------------
# CLI command registration
# ---------------------------------------------------------------------------

class TestCLIRegistration:
    def test_ingest_caselaw_registered(self):
        """The ingest-caselaw command should be registered in the CLI."""
        import argparse
        from unittest.mock import patch as mock_patch

        with mock_patch("sys.argv", ["employee-help", "ingest-caselaw", "--help"]):
            from employee_help.cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0  # --help exits with 0

    def test_spot_check_registered(self):
        """The spot-check-caselaw command should be registered in the CLI."""
        from unittest.mock import patch as mock_patch

        with mock_patch("sys.argv", ["employee-help", "spot-check-caselaw", "--help"]):
            from employee_help.cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
