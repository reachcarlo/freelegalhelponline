"""Tests for V2.1c.6 + V2.6.2: CaseChatService uses CaseContext and CaseArtifacts for richer system prompt context."""

from __future__ import annotations

import sqlite3

from employee_help.casefile.chat import CaseChatService
from employee_help.casefile.context import CaseContext, ClaimView, DateView, PartyView
from employee_help.casefile.context_builder import CaseContextBuilder
from employee_help.generation.prompts import PromptBuilder
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import ArtifactType, CaseArtifact, CaseFact, ExtractionMethod, FactCategory


CASE_ID = "case-ctx-int"
CASE_NAME = "Context Integration Test"
FILE_ID = "file-test"


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("""
        CREATE TABLE case_facts (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            category TEXT NOT NULL,
            fact_type TEXT NOT NULL,
            value TEXT NOT NULL,
            source_file_id TEXT,
            extraction_method TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            confirmed INTEGER NOT NULL DEFAULT 0,
            superseded_by TEXT,
            effective_date TEXT,
            created_at TEXT NOT NULL
        )
    """)
    return conn


def _make_fact(
    category: FactCategory,
    fact_type: str,
    value: dict,
) -> CaseFact:
    return CaseFact(
        case_id=CASE_ID,
        category=category,
        fact_type=fact_type,
        value=value,
        source_file_id=FILE_ID,
        extraction_method=ExtractionMethod.REGEX,
        confidence=0.7,
    )


def _seed_facts(storage: CaseFactStorage) -> None:
    """Seed a realistic set of facts for integration testing."""
    storage.add_fact(_make_fact(
        FactCategory.PARTY, "plaintiff",
        {"name": "Jane Doe", "role": "plaintiff", "party_type": "individual"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.PARTY, "defendant",
        {"name": "Acme Corp", "role": "defendant", "party_type": "entity"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.COURT, "court_info",
        {"court": "Superior Court", "county": "Los Angeles", "judge": "Hon. Smith"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.CLAIM, "feha_discrimination",
        {"claim_type": "feha_discrimination", "status": "active", "protected_class": "race"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.CLAIM, "wrongful_termination",
        {"claim_type": "wrongful_termination", "status": "active"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.DATE, "filing_date",
        {"label": "Complaint filed", "date": "2026-01-15", "date_type": "filing"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.EMPLOYMENT, "employer",
        {"employer": "Acme Corp", "position": "Manager", "start_date": "2020-03-01", "end_date": "2025-12-15"},
    ))
    storage.add_fact(_make_fact(
        FactCategory.FINANCIAL, "demand",
        {"label": "Initial demand", "amount": 500000.0, "date": "2026-02-01"},
    ))


def _build_service(
    case_fact_storage: CaseFactStorage,
    case_storage: CaseStorage | None = None,
) -> CaseChatService:
    """Build a CaseChatService with context_builder + case_fact_storage wired."""
    return CaseChatService(
        case_vector_store=None,
        embedding_service=None,
        retrieval_service=None,
        llm_client=None,
        prompt_builder=PromptBuilder(),
        case_storage=case_storage,
        context_builder=CaseContextBuilder(),
        case_fact_storage=case_fact_storage,
    )


class TestCaseChatContextIntegration:
    """CaseChatService builds CaseContext and injects it into system prompt."""

    def test_system_prompt_includes_party_names(self):
        """System prompt contains party names from extracted facts."""
        conn = _make_db()
        try:
            storage = CaseFactStorage(conn=conn)
            _seed_facts(storage)
            service = _build_service(storage)

            ctx = service._build_case_context(CASE_ID)
            prompt = service.build_case_system_prompt([], case_context=ctx)

            assert "Jane Doe" in prompt
            assert "Acme Corp" in prompt
            assert "plaintiff" in prompt
            assert "defendant" in prompt
        finally:
            conn.close()

    def test_system_prompt_includes_claims(self):
        """System prompt contains claim types and protected classes."""
        conn = _make_db()
        try:
            storage = CaseFactStorage(conn=conn)
            _seed_facts(storage)
            service = _build_service(storage)

            ctx = service._build_case_context(CASE_ID)
            prompt = service.build_case_system_prompt([], case_context=ctx)

            assert "Feha Discrimination" in prompt
            assert "Wrongful Termination" in prompt
            assert "race" in prompt
            assert "active" in prompt
        finally:
            conn.close()

    def test_system_prompt_includes_dates_and_court(self):
        """System prompt contains key dates and court information."""
        conn = _make_db()
        try:
            storage = CaseFactStorage(conn=conn)
            _seed_facts(storage)
            service = _build_service(storage)

            ctx = service._build_case_context(CASE_ID)
            prompt = service.build_case_system_prompt([], case_context=ctx)

            assert "Complaint filed" in prompt
            assert "2026-01-15" in prompt
            assert "Superior Court" in prompt
            assert "Los Angeles" in prompt
            assert "Hon. Smith" in prompt
        finally:
            conn.close()

    def test_system_prompt_includes_employment_and_financials(self):
        """System prompt contains employment history and financial events."""
        conn = _make_db()
        try:
            storage = CaseFactStorage(conn=conn)
            _seed_facts(storage)
            service = _build_service(storage)

            ctx = service._build_case_context(CASE_ID)
            prompt = service.build_case_system_prompt([], case_context=ctx)

            # Employment
            assert "Manager" in prompt
            assert "2020-03-01" in prompt
            assert "2025-12-15" in prompt
            # Financial
            assert "Initial demand" in prompt
            assert "500000.00" in prompt
        finally:
            conn.close()

    def test_system_prompt_graceful_without_context(self):
        """System prompt renders correctly when no context builder is available."""
        service = CaseChatService(
            case_vector_store=None,
            embedding_service=None,
            retrieval_service=None,
            llm_client=None,
            prompt_builder=PromptBuilder(),
            case_storage=None,
        )

        # No context_builder or case_fact_storage → _build_case_context returns None
        ctx = service._build_case_context("any-id")
        assert ctx is None

        # System prompt still renders without case context
        prompt = service.build_case_system_prompt([], case_context=None)
        assert "LITIGAGENT" in prompt
        assert "Case Overview" not in prompt


# ── V2.6.2: CaseArtifact awareness in system prompt ──────────────────


def _make_case_storage_db() -> sqlite3.Connection:
    """Create an in-memory DB with case_artifacts table for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("""
        CREATE TABLE case_artifacts (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            tool_source TEXT NOT NULL,
            summary TEXT,
            file_path TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT
        )
    """)
    # Minimal tables for CaseStorage to work
    conn.execute("""
        CREATE TABLE cases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            user_id TEXT,
            organization_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE case_notes (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            file_id TEXT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    return conn


class TestCaseChatArtifactIntegration:
    """V2.6.2: System prompt includes CaseArtifact list."""

    def test_prompt_omits_artifacts_section_when_empty(self):
        """When no artifacts exist, the prompt has no Prior Work Products section."""
        conn = _make_case_storage_db()
        try:
            case_storage = CaseStorage(conn=conn)
            service = CaseChatService(
                case_vector_store=None,
                embedding_service=None,
                retrieval_service=None,
                llm_client=None,
                prompt_builder=PromptBuilder(),
                case_storage=case_storage,
            )

            artifacts = service.get_case_artifacts(CASE_ID)
            assert artifacts == []

            prompt = service.build_case_system_prompt([], case_artifacts=artifacts)
            assert "Prior Work Products" not in prompt
            assert "LITIGAGENT" in prompt
        finally:
            conn.close()

    def test_prompt_includes_multiple_artifacts(self):
        """When artifacts exist, they are listed in the Prior Work Products section."""
        conn = _make_case_storage_db()
        try:
            case_storage = CaseStorage(conn=conn)

            # Seed two artifacts
            case_storage.create_artifact(CaseArtifact(
                case_id=CASE_ID,
                artifact_type=ArtifactType.DISCOVERY,
                tool_source="srogs",
                summary="35 Special Interrogatories, Set One",
            ))
            case_storage.create_artifact(CaseArtifact(
                case_id=CASE_ID,
                artifact_type=ArtifactType.DISCOVERY,
                tool_source="objection_drafter",
                summary="Objections generated (12 requests, 28 objections)",
            ))

            service = CaseChatService(
                case_vector_store=None,
                embedding_service=None,
                retrieval_service=None,
                llm_client=None,
                prompt_builder=PromptBuilder(),
                case_storage=case_storage,
            )

            artifacts = service.get_case_artifacts(CASE_ID)
            assert len(artifacts) == 2

            prompt = service.build_case_system_prompt([], case_artifacts=artifacts)
            assert "Prior Work Products" in prompt
            assert "35 Special Interrogatories, Set One" in prompt
            assert "Objections generated (12 requests, 28 objections)" in prompt
            assert "Avoid regenerating" in prompt
        finally:
            conn.close()

    def test_prompt_combines_context_and_artifacts(self):
        """System prompt includes both CaseContext and CaseArtifacts together."""
        conn_facts = _make_db()
        conn_case = _make_case_storage_db()
        try:
            fact_storage = CaseFactStorage(conn=conn_facts)
            _seed_facts(fact_storage)
            case_storage = CaseStorage(conn=conn_case)

            case_storage.create_artifact(CaseArtifact(
                case_id=CASE_ID,
                artifact_type=ArtifactType.DISCOVERY,
                tool_source="rfpds",
                summary="22 Requests for Production, Set Two",
            ))

            service = CaseChatService(
                case_vector_store=None,
                embedding_service=None,
                retrieval_service=None,
                llm_client=None,
                prompt_builder=PromptBuilder(),
                case_storage=case_storage,
                context_builder=CaseContextBuilder(),
                case_fact_storage=fact_storage,
            )

            ctx = service._build_case_context(CASE_ID)
            artifacts = service.get_case_artifacts(CASE_ID)

            prompt = service.build_case_system_prompt(
                [], case_context=ctx, case_artifacts=artifacts
            )

            # CaseContext sections present
            assert "Case Overview" in prompt
            assert "Jane Doe" in prompt
            assert "Feha Discrimination" in prompt

            # Artifacts section present
            assert "Prior Work Products" in prompt
            assert "22 Requests for Production, Set Two" in prompt
        finally:
            conn_facts.close()
            conn_case.close()
