"""P2.6 integration tests: CaseChatService with obfuscation enabled.

Verifies that:
- Single-turn: PII in query/case results/notes is obfuscated before the LLM
  sees it, and the streamed response is deobfuscated before the user sees it.
- Multi-turn: conversation history is scanned for entity map reconstruction;
  same entities get same placeholders across turns.
- KB results (public law) are never obfuscated.
- Engine=None (disabled) preserves existing behavior exactly.
- Filenames are replaced with "Document N".
- SSN hard redaction in case results is irreversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from employee_help.casefile.chat import CaseChatService, CaseRetrievalResult
from employee_help.privacy.context import ObfuscationContext
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer
from employee_help.retrieval.service import RetrievalResult


# ── Helpers ──────────────────────────────────────────────────────


@dataclass
class FakeEmbeddingResult:
    dense_vector: list[float]


@dataclass
class FakeStreamChunk:
    text: str = ""
    is_final: bool = False
    citations: list = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    def __post_init__(self):
        if self.citations is None:
            self.citations = []


def _no_ner_engine() -> ObfuscationEngine:
    """Engine with regex-only recognition (no spaCy)."""
    rec = EntityRecognizer()
    rec._nlp = None
    rec._ner_loaded = True
    return ObfuscationEngine(recognizer=rec)


def _make_svc(
    obfuscation_engine: ObfuscationEngine | None = None,
    **overrides: Any,
) -> CaseChatService:
    """Build a CaseChatService with mock dependencies."""
    mock_cvs = MagicMock()
    mock_embedder = MagicMock()
    mock_retrieval = MagicMock()
    mock_llm = MagicMock()
    mock_prompt_builder = MagicMock()
    mock_case_storage = MagicMock()

    mock_embedder.embed_query.return_value = FakeEmbeddingResult(
        dense_vector=[0.1] * 768
    )
    mock_cvs.search_hybrid.return_value = []
    mock_retrieval.retrieve.return_value = []
    mock_case_storage.list_notes.return_value = []
    mock_prompt_builder._build_document_blocks.return_value = []
    mock_prompt_builder._trim_history.side_effect = lambda h, _: h
    mock_prompt_builder._load_template.side_effect = FileNotFoundError

    kwargs: dict[str, Any] = {
        "case_vector_store": mock_cvs,
        "embedding_service": mock_embedder,
        "retrieval_service": mock_retrieval,
        "llm_client": mock_llm,
        "prompt_builder": mock_prompt_builder,
        "case_storage": mock_case_storage,
        "obfuscation_engine": obfuscation_engine,
    }
    kwargs.update(overrides)
    return CaseChatService(**kwargs)


def _raw_case(
    chunk_id: str = "chunk-1",
    file_id: str = "file-1",
    case_id: str = "case-1",
    filename: str = "complaint.pdf",
    file_type: str = "pdf",
    heading: str = "complaint.pdf > Page 1",
    score: float = 0.85,
    content: str = "John Smith was terminated on March 15.",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "file_id": file_id,
        "case_id": case_id,
        "content": content,
        "heading_path": heading,
        "file_type": file_type,
        "original_filename": filename,
        "_relevance_score": score,
        "content_hash": f"hash-{chunk_id}",
    }


def _kb_result(
    chunk_id: int = 101,
    heading: str = "Labor Code > § 1102.5",
    category: str = "statutory_code",
    citation: str = "Cal. Lab. Code § 1102.5",
    score: float = 0.9,
    content: str = "Whistleblower protection statute.",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=10,
        source_id=1,
        content=content,
        heading_path=heading,
        content_category=category,
        citation=citation,
        relevance_score=score,
        source_url="https://leginfo.ca.gov/...",
        content_hash=f"kb-hash-{chunk_id}",
    )


def _setup_stream(svc: CaseChatService, response_text: str) -> None:
    """Configure mock LLM to stream the given response text."""
    chunks = [
        FakeStreamChunk(text=response_text),
        FakeStreamChunk(
            text="",
            is_final=True,
            model="claude-haiku-4-5-20251001",
            input_tokens=100,
            output_tokens=50,
        ),
    ]
    svc.llm_client.generate_stream.return_value = iter(chunks)
    svc.llm_client.generate_stream_multiturn.return_value = iter(chunks)


def _consume_stream(
    stream_result: tuple,
) -> tuple[str, list[CaseRetrievalResult], list[RetrievalResult]]:
    """Consume a generate_stream result and return full text + results."""
    text_stream, case_results, kb_results, _metadata = stream_result
    full_text = "".join(text_stream)
    return full_text, case_results, kb_results


# ── Single-turn obfuscation ─────────────────────────────────────


class TestSingleTurnObfuscation:
    """Verify obfuscation in single-turn generate_stream."""

    def test_query_is_obfuscated_before_llm(self):
        """The user message sent to LLM has PII replaced."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        _setup_stream(svc, "Analysis of the claim.")

        _consume_stream(svc.generate_stream(
            "What claims does john@acme.com have?", "case-1"
        ))

        call_args = svc.llm_client.generate_stream.call_args
        user_msg = call_args.kwargs.get("user_message", call_args[1].get("user_message", ""))
        assert "john@acme.com" not in user_msg
        assert "EMAIL_1" in user_msg

    def test_case_result_content_obfuscated(self):
        """Case file content sent to LLM has PII replaced."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: 555-123-4567")
        ]
        _setup_stream(svc, "Response.")

        _consume_stream(svc.generate_stream("question", "case-1"))

        call_args = svc.llm_client.generate_stream.call_args
        doc_blocks = call_args.kwargs.get(
            "document_blocks", call_args[1].get("document_blocks", [])
        )
        # Find case file block content
        case_block_text = ""
        for block in doc_blocks:
            if block.get("type") == "document":
                source = block["source"]
                for part in source.get("content", []):
                    case_block_text += part.get("text", "")

        assert "555-123-4567" not in case_block_text
        assert "PHONE_1" in case_block_text

    def test_case_filenames_replaced_with_document_n(self):
        """Filenames in document blocks are replaced with 'Document N'."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(filename="smith_termination_letter.pdf"),
            _raw_case(
                chunk_id="chunk-2",
                filename="acme_corp_contract.pdf",
                content="Contract terms.",
            ),
        ]
        _setup_stream(svc, "Response.")

        _consume_stream(svc.generate_stream("question", "case-1"))

        call_args = svc.llm_client.generate_stream.call_args
        doc_blocks = call_args.kwargs.get(
            "document_blocks", call_args[1].get("document_blocks", [])
        )
        titles = [b.get("title", "") for b in doc_blocks if b.get("type") == "document"]
        # Should have "Document 1" and "Document 2" titles
        assert any("Document 1" in t for t in titles)
        assert any("Document 2" in t for t in titles)
        # Real filenames should NOT appear
        assert all("smith_termination" not in t for t in titles)

    def test_response_is_deobfuscated(self):
        """LLM response with placeholders is deobfuscated for the user."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Email john@acme.com for details.")
        ]
        # LLM responds with placeholder
        _setup_stream(svc, "Contact EMAIL_1 for more info.")

        full_text, _, _ = _consume_stream(
            svc.generate_stream(
                "How do I contact them?", "case-1"
            )
        )

        assert "john@acme.com" in full_text
        assert "EMAIL_1" not in full_text

    def test_kb_results_not_obfuscated(self):
        """Knowledge base results (public law) pass through without obfuscation."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        # Only KB results, no case results
        svc.retrieval_service.retrieve.return_value = [
            _kb_result(content="Cal. Lab. Code § 1102.5 protects employees.")
        ]
        svc.prompt_builder._build_document_blocks.return_value = [
            {
                "type": "document",
                "source": {
                    "type": "content",
                    "content": [{"type": "text", "text": "Cal. Lab. Code § 1102.5"}],
                },
                "title": "Labor Code",
                "citations": {"enabled": True},
            }
        ]
        _setup_stream(svc, "Response.")

        _consume_stream(svc.generate_stream("question", "case-1"))

        # KB document blocks should be passed through unchanged
        call_args = svc.llm_client.generate_stream.call_args
        doc_blocks = call_args.kwargs.get(
            "document_blocks", call_args[1].get("document_blocks", [])
        )
        kb_text = ""
        for block in doc_blocks:
            if block.get("title") == "Labor Code":
                for part in block["source"]["content"]:
                    kb_text += part.get("text", "")
        assert "Cal. Lab. Code § 1102.5" in kb_text

    def test_case_results_returned_unobfuscated(self):
        """The case_results returned to caller have REAL filenames (not Document N)."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(filename="employment_contract.pdf")
        ]
        _setup_stream(svc, "Response.")

        _, case_results, _ = _consume_stream(
            svc.generate_stream("question", "case-1")
        )

        # Returned to API layer with original filename for source events
        assert case_results[0].original_filename == "employment_contract.pdf"

    def test_notes_obfuscated(self):
        """Attorney notes with PII are obfuscated before the LLM."""
        from types import SimpleNamespace

        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]

        # Set up notes with PII
        note = SimpleNamespace(
            content="Plaintiff SSN: 123-45-6789",
            file_id="f-1",
        )
        svc.case_storage.list_notes.return_value = [note]

        # Mock get_case_file for filename lookup
        mock_file = SimpleNamespace(original_filename="plaintiff_records.pdf")
        svc.case_storage.get_case_file.return_value = mock_file

        _setup_stream(svc, "Response.")
        _consume_stream(svc.generate_stream("question", "case-1"))

        # System prompt should not contain the SSN
        call_args = svc.llm_client.generate_stream.call_args
        system_prompt = call_args.kwargs.get(
            "system_prompt", call_args[1].get("system_prompt", "")
        )
        assert "123-45-6789" not in system_prompt
        assert "[REDACTED]" in system_prompt

    def test_ssn_in_case_content_hard_redacted(self):
        """SSN in case file content is hard-redacted (irreversible)."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Employee SSN: 123-45-6789 was filed.")
        ]
        # LLM responds with the redacted marker
        _setup_stream(svc, "The [REDACTED] was filed.")

        full_text, _, _ = _consume_stream(
            svc.generate_stream("question", "case-1")
        )

        # [REDACTED] stays as [REDACTED] — not reversed
        assert "[REDACTED]" in full_text


# ── Multi-turn obfuscation ──────────────────────────────────────


class TestMultiTurnObfuscation:
    """Verify obfuscation in multi-turn generate_stream_multiturn."""

    def test_history_scanned_before_current_turn(self):
        """Entities from history get same placeholders as current turn."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: 555-123-4567")
        ]
        _setup_stream(svc, "Call PHONE_1.")

        history = [
            {"role": "user", "content": "What about 555-123-4567?"},
            {"role": "assistant", "content": "That's the main number."},
        ]

        full_text, _, _ = _consume_stream(
            svc.generate_stream_multiturn(
                query="Can I call them?",
                case_id="case-1",
                conversation_history=history,
                turn_number=2,
            )
        )

        # Response deobfuscated correctly
        assert "555-123-4567" in full_text
        assert "PHONE_1" not in full_text

    def test_history_obfuscated_in_messages(self):
        """Conversation history sent to LLM has PII replaced."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        _setup_stream(svc, "Response.")

        history = [
            {"role": "user", "content": "Contact john@acme.com"},
            {"role": "assistant", "content": "I'll help with that."},
        ]

        _consume_stream(
            svc.generate_stream_multiturn(
                query="What next?",
                case_id="case-1",
                conversation_history=history,
                turn_number=2,
            )
        )

        call_args = svc.llm_client.generate_stream_multiturn.call_args
        messages = call_args.kwargs.get(
            "messages", call_args[1].get("messages", [])
        )

        # History messages should have PII replaced
        history_texts = " ".join(
            m["content"] for m in messages if isinstance(m["content"], str)
        )
        assert "john@acme.com" not in history_texts
        assert "EMAIL_1" in history_texts

    def test_multiturn_deterministic_placeholders(self):
        """Same entities across turns get same placeholder assignments."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Email: alice@test.com, Phone: 555-000-1111")
        ]
        _setup_stream(svc, "EMAIL_1 and PHONE_1.")

        # Turn 1
        result1 = svc.generate_stream(
            "What about alice@test.com?", "case-1"
        )
        text1 = "".join(result1[0])

        # Turn 2 — rebuild with history
        _setup_stream(svc, "EMAIL_1 and PHONE_1.")
        history = [
            {"role": "user", "content": "What about alice@test.com?"},
            {"role": "assistant", "content": text1},
        ]
        result2 = svc.generate_stream_multiturn(
            query="Tell me more about their phone",
            case_id="case-1",
            conversation_history=history,
            turn_number=2,
        )
        text2 = "".join(result2[0])

        # Both turns should resolve EMAIL_1 → alice@test.com
        assert "alice@test.com" in text1
        assert "alice@test.com" in text2

    def test_multiturn_new_entity_discovered_in_later_turn(self):
        """Entity discovered in turn 2 gets next available placeholder."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)

        # Turn 1: one email
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com")
        ]
        _setup_stream(svc, "Contact EMAIL_1.")
        result1 = svc.generate_stream("Who to contact?", "case-1")
        text1 = "".join(result1[0])

        # Turn 2: new email appears in case results
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                chunk_id="chunk-2",
                content="CC: bob@test.com and alice@test.com",
            )
        ]
        _setup_stream(svc, "Also contact EMAIL_2.")

        history = [
            {"role": "user", "content": "Who to contact?"},
            {"role": "assistant", "content": text1},
        ]
        result2 = svc.generate_stream_multiturn(
            query="Anyone else?",
            case_id="case-1",
            conversation_history=history,
            turn_number=2,
        )
        text2 = "".join(result2[0])

        # Turn 2: EMAIL_2 should resolve to bob@test.com
        assert "bob@test.com" in text2


# ── No-engine (disabled) ────────────────────────────────────────


class TestNoEngine:
    """Verify that engine=None preserves existing behavior exactly."""

    def test_single_turn_no_obfuscation(self):
        """Without engine, query passes through verbatim."""
        svc = _make_svc(obfuscation_engine=None)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact john@acme.com")
        ]
        _setup_stream(svc, "Contact john@acme.com for help.")

        full_text, _, _ = _consume_stream(
            svc.generate_stream("Email john@acme.com", "case-1")
        )

        # Query passes through unchanged
        call_args = svc.llm_client.generate_stream.call_args
        user_msg = call_args.kwargs.get(
            "user_message", call_args[1].get("user_message", "")
        )
        assert "john@acme.com" in user_msg
        # Response passes through unchanged
        assert "john@acme.com" in full_text

    def test_multiturn_no_obfuscation(self):
        """Without engine, multi-turn history passes through verbatim."""
        svc = _make_svc(obfuscation_engine=None)
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        _setup_stream(svc, "Response.")

        history = [
            {"role": "user", "content": "Email john@acme.com"},
            {"role": "assistant", "content": "OK."},
        ]

        _consume_stream(
            svc.generate_stream_multiturn(
                query="Follow up",
                case_id="case-1",
                conversation_history=history,
                turn_number=2,
            )
        )

        call_args = svc.llm_client.generate_stream_multiturn.call_args
        messages = call_args.kwargs.get(
            "messages", call_args[1].get("messages", [])
        )
        history_texts = " ".join(
            m["content"] for m in messages if isinstance(m["content"], str)
        )
        assert "john@acme.com" in history_texts


# ── Helper methods ──────────────────────────────────────────────


class TestObfuscateHelpers:
    """Test _obfuscate_case_results and _obfuscate_notes directly."""

    def test_obfuscate_case_results_content_and_heading(self):
        """Content and heading_path are obfuscated, file_type preserved."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)

        ctx = engine.create_context()
        results = [
            CaseRetrievalResult(
                chunk_id="c-1",
                file_id="f-1",
                case_id="case-1",
                content="Email: alice@test.com",
                heading_path="complaint.pdf > Page 1",
                file_type="pdf",
                original_filename="complaint.pdf",
                relevance_score=0.9,
            )
        ]

        obfuscated = svc._obfuscate_case_results(results, ctx)

        assert len(obfuscated) == 1
        assert "alice@test.com" not in obfuscated[0].content
        assert "EMAIL_1" in obfuscated[0].content
        assert obfuscated[0].file_type == "pdf"
        assert obfuscated[0].original_filename == "Document 1"
        assert obfuscated[0].chunk_id == "c-1"  # preserved

    def test_obfuscate_notes_content_and_filename(self):
        """Note content is obfuscated, filename replaced."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)

        ctx = engine.create_context()
        notes = [
            {
                "content": "Call 555-123-4567 about the case.",
                "file_id": "f-1",
                "filename": "witness_list.pdf",
            },
            {
                "content": "General note.",
                "file_id": None,
                "filename": None,
            },
        ]

        obfuscated = svc._obfuscate_notes(notes, ctx)

        assert len(obfuscated) == 2
        assert "555-123-4567" not in obfuscated[0]["content"]
        assert "PHONE_1" in obfuscated[0]["content"]
        assert obfuscated[0]["filename"] == "Document 1"
        # Second note has no filename — stays None
        assert obfuscated[1]["filename"] is None
        assert obfuscated[1]["content"] == "General note."

    def test_obfuscate_case_results_sequential_filenames(self):
        """Multiple results get sequential Document N filenames."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)

        ctx = engine.create_context()
        results = [
            CaseRetrievalResult(
                chunk_id=f"c-{i}",
                file_id=f"f-{i}",
                case_id="case-1",
                content=f"Content {i}",
                heading_path="",
                file_type="pdf",
                original_filename=f"file_{i}.pdf",
                relevance_score=0.5,
            )
            for i in range(3)
        ]

        obfuscated = svc._obfuscate_case_results(results, ctx)

        assert obfuscated[0].original_filename == "Document 1"
        assert obfuscated[1].original_filename == "Document 2"
        assert obfuscated[2].original_filename == "Document 3"


# ── Edge cases ──────────────────────────────────────────────────


class TestObfuscationEdgeCases:
    """Edge cases in the chat integration."""

    def test_empty_results_no_obfuscation_crash(self):
        """Empty retrieval results → empty stream, no crash."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        # No case or KB results → empty stream path
        text_stream, case_results, kb_results, _ = svc.generate_stream(
            "question", "case-1"
        )
        full_text = "".join(text_stream)

        assert "couldn't find" in full_text
        assert case_results == []

    def test_query_with_legal_citation_preserved(self):
        """Legal citations in user query are NOT obfuscated."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        _setup_stream(svc, "Response about the code section.")

        _consume_stream(
            svc.generate_stream(
                "What does Cal. Lab. Code § 1102.5 say?", "case-1"
            )
        )

        call_args = svc.llm_client.generate_stream.call_args
        user_msg = call_args.kwargs.get(
            "user_message", call_args[1].get("user_message", "")
        )
        assert "Cal. Lab. Code § 1102.5" in user_msg

    def test_mixed_pii_and_citations_in_content(self):
        """Case content with both PII and citations: PII obfuscated, citations preserved."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                content=(
                    "John emailed alice@test.com about "
                    "Cal. Lab. Code § 1102.5 violations."
                )
            ),
        ]
        _setup_stream(svc, "Response.")

        _consume_stream(svc.generate_stream("question", "case-1"))

        call_args = svc.llm_client.generate_stream.call_args
        doc_blocks = call_args.kwargs.get(
            "document_blocks", call_args[1].get("document_blocks", [])
        )
        case_text = ""
        for block in doc_blocks:
            if block.get("type") == "document":
                for part in block["source"]["content"]:
                    case_text += part.get("text", "")

        assert "alice@test.com" not in case_text
        assert "EMAIL_1" in case_text
        assert "Cal. Lab. Code § 1102.5" in case_text

    def test_multiturn_empty_history(self):
        """Multi-turn with empty history behaves like single-turn."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: 555-123-4567")
        ]
        _setup_stream(svc, "Call PHONE_1.")

        full_text, _, _ = _consume_stream(
            svc.generate_stream_multiturn(
                query="Who to call?",
                case_id="case-1",
                conversation_history=[],
                turn_number=1,
            )
        )

        assert "555-123-4567" in full_text

    def test_obfuscation_context_is_ephemeral(self):
        """Each call to generate_stream creates a fresh context."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Email: alice@test.com")
        ]

        # Call 1
        _setup_stream(svc, "EMAIL_1 is the contact.")
        text1, _, _ = _consume_stream(
            svc.generate_stream("question", "case-1")
        )

        # Call 2 with different PII — should get EMAIL_1 (fresh context)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Email: bob@test.com")
        ]
        _setup_stream(svc, "EMAIL_1 is the contact.")
        text2, _, _ = _consume_stream(
            svc.generate_stream("question", "case-1")
        )

        # Each call maps EMAIL_1 to its own context's entity
        assert "alice@test.com" in text1
        assert "bob@test.com" in text2

    def test_multiple_entity_types_in_single_call(self):
        """Multiple PII types in one call are all obfuscated."""
        engine = _no_ner_engine()
        svc = _make_svc(obfuscation_engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                content=(
                    "Employee SSN: 123-45-6789, "
                    "Email: alice@test.com, "
                    "Phone: 555-000-1111"
                )
            ),
        ]
        _setup_stream(svc, "EMAIL_1 and PHONE_1.")

        full_text, _, _ = _consume_stream(
            svc.generate_stream("question", "case-1")
        )

        # Verify obfuscation in what was sent to LLM
        call_args = svc.llm_client.generate_stream.call_args
        doc_blocks = call_args.kwargs.get(
            "document_blocks", call_args[1].get("document_blocks", [])
        )
        case_text = ""
        for block in doc_blocks:
            if block.get("type") == "document":
                for part in block["source"]["content"]:
                    case_text += part.get("text", "")

        assert "123-45-6789" not in case_text
        assert "[REDACTED]" in case_text
        assert "alice@test.com" not in case_text
        assert "555-000-1111" not in case_text

        # Deobfuscated response
        assert "alice@test.com" in full_text
        assert "555-000-1111" in full_text
