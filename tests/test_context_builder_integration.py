"""Tests for V2.1c.4: CaseContextBuilder singleton in deps.py, injected into CaseChatService."""

from __future__ import annotations

import sqlite3

from employee_help.casefile.chat import CaseChatService
from employee_help.casefile.context_builder import CaseContextBuilder
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import CaseFact, ExtractionMethod, FactCategory


CASE_ID = "case-builder-int"
CASE_NAME = "Builder Integration Test"
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


class TestContextBuilderSingleton:
    """CaseContextBuilder singleton wiring in deps.py and injection into CaseChatService."""

    def test_deps_context_builder_getter(self):
        """get_context_builder() returns CaseContextBuilder after init, None before."""
        from employee_help.api import deps

        # Before init: should be None
        old = deps._context_builder
        deps._context_builder = None
        assert deps.get_context_builder() is None

        # After setting: should return the instance
        builder = CaseContextBuilder()
        deps._context_builder = builder
        assert deps.get_context_builder() is builder

        # Restore
        deps._context_builder = old

    def test_case_chat_service_receives_context_builder(self):
        """CaseChatService stores context_builder when injected via constructor."""
        builder = CaseContextBuilder()

        # CaseChatService accepts context_builder as keyword argument
        service = CaseChatService(
            case_vector_store=None,
            embedding_service=None,
            retrieval_service=None,
            llm_client=None,
            prompt_builder=None,
            case_storage=None,
            context_builder=builder,
        )
        assert service._context_builder is builder

    def test_case_chat_service_context_builder_defaults_none(self):
        """CaseChatService defaults context_builder to None if not provided."""
        service = CaseChatService(
            case_vector_store=None,
            embedding_service=None,
            retrieval_service=None,
            llm_client=None,
            prompt_builder=None,
            case_storage=None,
        )
        assert service._context_builder is None

    def test_injected_builder_produces_valid_context(self):
        """Builder injected into CaseChatService can build CaseContext from facts."""
        conn = _make_db()
        try:
            storage = CaseFactStorage(conn=conn)
            storage.add_fact(_make_fact(
                FactCategory.PARTY, "plaintiff",
                {"name": "Jane Doe", "role": "plaintiff", "party_type": "individual"},
            ))
            storage.add_fact(_make_fact(
                FactCategory.COURT, "court_info",
                {"court": "Superior Court", "county": "Sacramento"},
            ))

            builder = CaseContextBuilder()
            service = CaseChatService(
                case_vector_store=None,
                embedding_service=None,
                retrieval_service=None,
                llm_client=None,
                prompt_builder=None,
                case_storage=None,
                context_builder=builder,
            )

            # Use the injected builder to build context
            ctx = service._context_builder.build(CASE_ID, CASE_NAME, storage)
            assert ctx.case_id == CASE_ID
            assert ctx.case_name == CASE_NAME
            assert len(ctx.parties) == 1
            assert ctx.parties[0].name == "Jane Doe"
            assert ctx.court is not None
            assert ctx.court.court == "Superior Court"
            assert ctx.fact_count == 2
            assert ctx.plaintiff_names == ["Jane Doe"]
        finally:
            conn.close()
