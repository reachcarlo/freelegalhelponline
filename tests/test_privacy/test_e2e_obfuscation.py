"""P2.9 E2E integration tests: obfuscation through chat + objection paths.

Verifies the four P2.9 gate-check requirements:
1. Anthropic receives obfuscated text (check via mock LLM call args).
2. User receives deobfuscated response with real names.
3. Multi-turn consistency holds across 3+ turns.
4. Legal citations in response are preserved correctly.

Also covers cross-path consistency, context isolation, and complex
real-world scenarios with mixed entity types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from employee_help.casefile.chat import CaseChatService, CaseRetrievalResult
from employee_help.discovery.objections.analyzer import ObjectionAnalyzer
from employee_help.discovery.objections.knowledge_base import ObjectionKnowledgeBase
from employee_help.discovery.objections.models import (
    ObjectionRequest,
    ResponseDiscoveryType,
    Verbosity,
    PartyRole,
)
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer
from employee_help.retrieval.service import RetrievalResult


# ── Shared helpers ──────────────────────────────────────────────


def _no_ner_engine() -> ObfuscationEngine:
    """Engine with regex-only recognition (no spaCy)."""
    rec = EntityRecognizer()
    rec._nlp = None
    rec._ner_loaded = True
    return ObfuscationEngine(recognizer=rec)


# ── Chat helpers ────────────────────────────────────────────────


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


def _make_chat_svc(
    engine: ObfuscationEngine | None = None,
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

    return CaseChatService(
        case_vector_store=mock_cvs,
        embedding_service=mock_embedder,
        retrieval_service=mock_retrieval,
        llm_client=mock_llm,
        prompt_builder=mock_prompt_builder,
        case_storage=mock_case_storage,
        obfuscation_engine=engine,
    )


def _raw_case(
    chunk_id: str = "chunk-1",
    content: str = "John Smith was terminated on March 15.",
    filename: str = "complaint.pdf",
    **overrides: Any,
) -> dict[str, Any]:
    defaults = {
        "chunk_id": chunk_id,
        "file_id": "file-1",
        "case_id": "case-1",
        "content": content,
        "heading_path": f"{filename} > Page 1",
        "file_type": "pdf",
        "original_filename": filename,
        "_relevance_score": 0.85,
        "content_hash": f"hash-{chunk_id}",
    }
    defaults.update(overrides)
    return defaults


def _setup_chat_stream(svc: CaseChatService, text: str) -> None:
    """Configure mock LLM to stream the given response text."""
    chunks = [
        FakeStreamChunk(text=text),
        FakeStreamChunk(
            text="", is_final=True,
            model="claude-haiku-4-5-20251001",
            input_tokens=100, output_tokens=50,
        ),
    ]
    svc.llm_client.generate_stream.return_value = iter(chunks)
    svc.llm_client.generate_stream_multiturn.return_value = iter(chunks)


def _consume_chat(stream_result: tuple) -> str:
    """Consume a chat stream and return full text."""
    text_stream = stream_result[0]
    return "".join(text_stream)


# ── Objection helpers ───────────────────────────────────────────


def _mock_llm_response(
    analyses: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "tool_input": {"request_analyses": analyses},
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "claude-haiku-4-5-20251001",
    }


def _make_objection_analyzer(
    llm_response: dict[str, Any] | None = None,
    engine: ObfuscationEngine | None = None,
) -> tuple[ObjectionAnalyzer, MagicMock]:
    mock_llm = MagicMock()
    if llm_response is not None:
        mock_llm.generate_with_tools.return_value = llm_response

    kb = ObjectionKnowledgeBase()
    analyzer = ObjectionAnalyzer(
        mock_llm, kb, obfuscation_engine=engine
    )
    return analyzer, mock_llm


# ── Gate 1: Anthropic receives obfuscated text ─────────────────


class TestGate1AnthropicReceivesObfuscated:
    """Gate check 1: LLM receives obfuscated text, never real PII."""

    def test_chat_path_all_pii_obfuscated(self):
        """Chat path: query + case content + notes are fully obfuscated."""
        from types import SimpleNamespace

        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)

        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Employee jane@corp.com called (555) 111-2222."),
        ]
        note = SimpleNamespace(
            content="Witness bob@example.org saw it.", file_id="f-1",
        )
        svc.case_storage.list_notes.return_value = [note]
        mock_file = SimpleNamespace(original_filename="witness.pdf")
        svc.case_storage.get_case_file.return_value = mock_file

        _setup_chat_stream(svc, "Analysis complete.")
        _consume_chat(svc.generate_stream(
            "What about jane@corp.com?", "case-1"
        ))

        call_args = svc.llm_client.generate_stream.call_args

        # User message
        user_msg = call_args.kwargs.get("user_message", "")
        assert "jane@corp.com" not in user_msg
        assert "EMAIL_1" in user_msg

        # Document blocks (case content)
        doc_blocks = call_args.kwargs.get("document_blocks", [])
        all_block_text = ""
        for block in doc_blocks:
            if block.get("type") == "document":
                for part in block["source"]["content"]:
                    all_block_text += part.get("text", "")
        assert "jane@corp.com" not in all_block_text
        assert "(555) 111-2222" not in all_block_text

        # System prompt (notes)
        system_prompt = call_args.kwargs.get("system_prompt", "")
        assert "bob@example.org" not in system_prompt

    def test_objection_path_pii_obfuscated(self):
        """Objection path: request text is obfuscated before LLM."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_objection_analyzer(response, engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text=(
                "Produce all emails from alice@test.com "
                "and phone records for (555) 999-0000."
            ),
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_msg = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "alice@test.com" not in user_msg
        assert "(555) 999-0000" not in user_msg
        assert "EMAIL_1" in user_msg
        assert "PHONE_1" in user_msg


# ── Gate 2: User receives deobfuscated response ───────────────


class TestGate2UserReceivesDeobfuscated:
    """Gate check 2: User sees real PII in the final response."""

    def test_chat_response_deobfuscated(self):
        """Chat: LLM response with placeholders is deobfuscated."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com, phone (555) 333-4444"),
        ]
        _setup_chat_stream(
            svc,
            "Please contact EMAIL_1 at PHONE_1 for more details.",
        )

        full_text = _consume_chat(
            svc.generate_stream("Who to contact?", "case-1")
        )

        assert "alice@test.com" in full_text
        assert "(555) 333-4444" in full_text
        assert "EMAIL_1" not in full_text
        assert "PHONE_1" not in full_text

    def test_objection_explanation_deobfuscated(self):
        """Objection: explanation with placeholders is deobfuscated."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": (
                    "The request for EMAIL_1 records raises privacy concerns. "
                    "PHONE_1 should not be disclosed."
                ),
                "strength": "high",
            }],
        }])
        analyzer, _ = _make_objection_analyzer(response, engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text=(
                "Produce emails from alice@test.com "
                "and calls to (555) 999-0000."
            ),
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)

        explanation = result.objections[0].explanation
        assert "alice@test.com" in explanation
        assert "(555) 999-0000" in explanation
        assert "EMAIL_1" not in explanation
        assert "PHONE_1" not in explanation


# ── Gate 3: Multi-turn consistency (3+ turns) ─────────────────


class TestGate3MultiturnThreePlusTurns:
    """Gate check 3: Multi-turn consistency holds across 3+ turns."""

    def test_three_turn_same_entity_consistency(self):
        """Same email across 3 turns always resolves to the same real value."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]

        # Turn 1
        _setup_chat_stream(svc, "EMAIL_1 is the primary contact.")
        text1 = _consume_chat(
            svc.generate_stream("Who is alice@test.com?", "case-1")
        )
        assert "alice@test.com" in text1

        # Turn 2
        _setup_chat_stream(svc, "Yes, EMAIL_1 was involved in the incident.")
        history = [
            {"role": "user", "content": "Who is alice@test.com?"},
            {"role": "assistant", "content": text1},
        ]
        text2 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Was she involved?",
                case_id="case-1",
                conversation_history=history,
                turn_number=2,
            )
        )
        assert "alice@test.com" in text2

        # Turn 3
        _setup_chat_stream(svc, "EMAIL_1 should be deposed.")
        history.extend([
            {"role": "user", "content": "Was she involved?"},
            {"role": "assistant", "content": text2},
        ])
        text3 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Next steps?",
                case_id="case-1",
                conversation_history=history,
                turn_number=3,
            )
        )
        assert "alice@test.com" in text3
        assert "EMAIL_1" not in text3

    def test_four_turn_new_entities_each_turn(self):
        """New entities discovered in later turns get incrementing placeholders."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)

        # Turn 1: one email
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1 is the plaintiff.")
        text1 = _consume_chat(
            svc.generate_stream("Who is involved?", "case-1")
        )
        assert "alice@test.com" in text1

        # Turn 2: second email appears
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                chunk_id="c-2",
                content="CC: bob@test.com about the case.",
            ),
        ]
        _setup_chat_stream(svc, "EMAIL_2 is the manager.")
        history = [
            {"role": "user", "content": "Who is involved?"},
            {"role": "assistant", "content": text1},
        ]
        text2 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Anyone else?",
                case_id="case-1",
                conversation_history=history,
                turn_number=2,
            )
        )
        assert "bob@test.com" in text2

        # Turn 3: phone number appears
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                chunk_id="c-3",
                content="Call (555) 777-8888 for the witness.",
            ),
        ]
        _setup_chat_stream(svc, "PHONE_1 is the witness line.")
        history.extend([
            {"role": "user", "content": "Anyone else?"},
            {"role": "assistant", "content": text2},
        ])
        text3 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Any witnesses?",
                case_id="case-1",
                conversation_history=history,
                turn_number=3,
            )
        )
        assert "(555) 777-8888" in text3

        # Turn 4: reference to all prior entities
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1, EMAIL_2, and PHONE_1 are key.")
        history.extend([
            {"role": "user", "content": "Any witnesses?"},
            {"role": "assistant", "content": text3},
        ])
        text4 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Summary?",
                case_id="case-1",
                conversation_history=history,
                turn_number=4,
            )
        )
        assert "alice@test.com" in text4
        assert "bob@test.com" in text4
        assert "(555) 777-8888" in text4

    def test_three_turn_history_obfuscated_consistently(self):
        """History messages sent to LLM across 3 turns are always obfuscated."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]

        # Turn 1
        _setup_chat_stream(svc, "EMAIL_1 confirmed.")
        text1 = _consume_chat(
            svc.generate_stream("Tell me about alice@test.com", "case-1")
        )

        # Turn 2
        _setup_chat_stream(svc, "Yes.")
        history = [
            {"role": "user", "content": "Tell me about alice@test.com"},
            {"role": "assistant", "content": text1},
        ]
        text2 = _consume_chat(
            svc.generate_stream_multiturn(
                query="Confirm?", case_id="case-1",
                conversation_history=history, turn_number=2,
            )
        )

        # Turn 3 — verify history sent to LLM
        _setup_chat_stream(svc, "Done.")
        history.extend([
            {"role": "user", "content": "Confirm?"},
            {"role": "assistant", "content": text2},
        ])
        _consume_chat(
            svc.generate_stream_multiturn(
                query="Finalize?", case_id="case-1",
                conversation_history=history, turn_number=3,
            )
        )

        call_args = svc.llm_client.generate_stream_multiturn.call_args
        messages = call_args.kwargs.get("messages", [])
        all_text = " ".join(
            m["content"] for m in messages if isinstance(m["content"], str)
        )
        # History should contain placeholders, not real PII
        assert "alice@test.com" not in all_text
        assert "EMAIL_1" in all_text


# ── Gate 4: Legal citations preserved ─────────────────────────


class TestGate4LegalCitationsPreserved:
    """Gate check 4: Legal citations in response are preserved correctly."""

    def test_chat_response_legal_citations_intact(self):
        """Legal citations in LLM chat response are not corrupted."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(
                content=(
                    "Plaintiff alice@test.com alleges violation of "
                    "Cal. Lab. Code § 1102.5."
                ),
            ),
        ]
        _setup_chat_stream(
            svc,
            (
                "Under Cal. Lab. Code § 1102.5, EMAIL_1 has a valid "
                "whistleblower claim. See also Cal. Gov. Code § 12940(a)."
            ),
        )

        full_text = _consume_chat(
            svc.generate_stream("What claims exist?", "case-1")
        )

        assert "Cal. Lab. Code § 1102.5" in full_text
        assert "Cal. Gov. Code § 12940(a)" in full_text
        assert "alice@test.com" in full_text

    def test_objection_citations_in_explanation_preserved(self):
        """Legal citations in objection explanation are not corrupted."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": (
                    "Under Cal. Const. art. I, § 1, EMAIL_1 has a "
                    "constitutional privacy right. Cal. Civ. Proc. Code "
                    "§ 2031.060 protects sensitive data."
                ),
                "strength": "high",
            }],
        }])
        analyzer, _ = _make_objection_analyzer(response, engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Produce emails to alice@test.com.",
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        result = analyzer.analyze_single(req)

        explanation = result.objections[0].explanation
        assert "Cal. Const. art. I, § 1" in explanation
        assert "Cal. Civ. Proc. Code § 2031.060" in explanation
        assert "alice@test.com" in explanation
        assert "EMAIL_1" not in explanation

    def test_chat_input_mixed_citations_and_pii(self):
        """In user query, citations are preserved while PII is obfuscated."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Relevant document."),
        ]
        _setup_chat_stream(svc, "Analysis.")

        _consume_chat(svc.generate_stream(
            "Does Cal. Lab. Code § 226 require alice@test.com to get stubs?",
            "case-1",
        ))

        call_args = svc.llm_client.generate_stream.call_args
        user_msg = call_args.kwargs.get("user_message", "")
        assert "Cal. Lab. Code § 226" in user_msg
        assert "alice@test.com" not in user_msg
        assert "EMAIL_1" in user_msg


# ── Cross-path consistency ────────────────────────────────────


class TestCrossPathConsistency:
    """Same engine produces consistent behavior across chat + objection."""

    def test_same_pii_same_behavior_both_paths(self):
        """Same email is obfuscated identically through both paths."""
        engine = _no_ner_engine()

        # Chat path
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1 is the contact.")
        chat_text = _consume_chat(
            svc.generate_stream("Who is alice@test.com?", "case-1")
        )

        # Objection path
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "EMAIL_1 is a private address.",
                "strength": "high",
            }],
        }])
        analyzer, _ = _make_objection_analyzer(response, engine=engine)
        req = ObjectionRequest(
            request_number=1,
            request_text="Produce emails to alice@test.com.",
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        objection_result = analyzer.analyze_single(req)

        # Both paths should resolve EMAIL_1 → alice@test.com
        assert "alice@test.com" in chat_text
        assert "alice@test.com" in objection_result.objections[0].explanation

    def test_ssn_hard_redacted_both_paths(self):
        """SSN is irreversibly redacted through both chat and objection."""
        engine = _no_ner_engine()

        # Chat path
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Employee SSN: 123-45-6789."),
        ]
        _setup_chat_stream(svc, "[REDACTED] was filed.")
        chat_text = _consume_chat(
            svc.generate_stream("What SSN?", "case-1")
        )
        assert "[REDACTED]" in chat_text
        assert "123-45-6789" not in chat_text

        # Objection path
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "[REDACTED] is sensitive.",
                "strength": "high",
            }],
        }])
        analyzer, _ = _make_objection_analyzer(response, engine=engine)
        req = ObjectionRequest(
            request_number=1,
            request_text="Produce employee SSN 987-65-4321.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)
        assert "[REDACTED]" in result.objections[0].explanation
        assert "987-65-4321" not in result.objections[0].explanation


# ── Context isolation ─────────────────────────────────────────


class TestContextIsolation:
    """Separate API calls use independent ephemeral contexts."""

    def test_chat_calls_dont_leak_entities(self):
        """Two sequential chat calls have isolated entity maps."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)

        # Call 1: alice@test.com → EMAIL_1
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1 is the contact.")
        text1 = _consume_chat(
            svc.generate_stream("question", "case-1")
        )
        assert "alice@test.com" in text1

        # Call 2: bob@test.com → EMAIL_1 (fresh context, not EMAIL_2)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: bob@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1 is the contact.")
        text2 = _consume_chat(
            svc.generate_stream("question", "case-1")
        )
        assert "bob@test.com" in text2
        assert "alice@test.com" not in text2

    def test_objection_calls_dont_leak_entities(self):
        """Two sequential objection calls have isolated entity maps."""
        engine = _no_ner_engine()

        # Call 1
        response1 = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "EMAIL_1 is private.",
                "strength": "medium",
            }],
        }])
        analyzer, mock_llm = _make_objection_analyzer(response1, engine=engine)
        req1 = ObjectionRequest(
            1, "Emails to alice@test.com.",
            ResponseDiscoveryType.RFPS,
        )
        result1 = analyzer.analyze_single(req1)
        assert "alice@test.com" in result1.objections[0].explanation

        # Call 2 — fresh context, EMAIL_1 maps to bob
        response2 = _mock_llm_response([{
            "request_number": 2,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "EMAIL_1 is private.",
                "strength": "medium",
            }],
        }])
        mock_llm.generate_with_tools.return_value = response2
        req2 = ObjectionRequest(
            2, "Emails to bob@test.com.",
            ResponseDiscoveryType.RFPS,
        )
        result2 = analyzer.analyze_single(req2)
        assert "bob@test.com" in result2.objections[0].explanation
        assert "alice@test.com" not in result2.objections[0].explanation

    def test_chat_and_objection_dont_share_context(self):
        """Chat and objection calls on the same engine are isolated."""
        engine = _no_ner_engine()

        # Chat call: alice → EMAIL_1
        svc = _make_chat_svc(engine=engine)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "EMAIL_1 is the contact.")
        chat_text = _consume_chat(
            svc.generate_stream("question", "case-1")
        )
        assert "alice@test.com" in chat_text

        # Objection call: bob → EMAIL_1 (independent context)
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "EMAIL_1 is private.",
                "strength": "medium",
            }],
        }])
        analyzer, _ = _make_objection_analyzer(response, engine=engine)
        req = ObjectionRequest(
            1, "Emails to bob@test.com.",
            ResponseDiscoveryType.RFPS,
        )
        result = analyzer.analyze_single(req)
        # EMAIL_1 should resolve to bob, not alice
        assert "bob@test.com" in result.objections[0].explanation


# ── Complex real-world scenario ───────────────────────────────


class TestComplexRealWorldScenario:
    """Realistic legal document with mixed entity types."""

    def test_full_pipeline_complex_content(self):
        """Full chat pipeline with multiple entity types + legal citations."""
        engine = _no_ner_engine()
        svc = _make_chat_svc(engine=engine)

        complex_content = (
            "On 2024-01-15, PERSON_1 emailed jane@acme.com (Employee SSN: "
            "123-45-6789) about a Cal. Lab. Code § 1102.5 violation. "
            "Witness at (555) 222-3333 confirmed harassment per "
            "Cal. Gov. Code § 12940(a)."
        )
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content=complex_content),
        ]

        llm_response = (
            "Under Cal. Lab. Code § 1102.5, EMAIL_1 has a whistleblower "
            "claim. The witness at PHONE_1 corroborates the "
            "Cal. Gov. Code § 12940(a) harassment. The [REDACTED] was "
            "in the records."
        )
        _setup_chat_stream(svc, llm_response)

        full_text = _consume_chat(
            svc.generate_stream("Analyze this case.", "case-1")
        )

        # PII deobfuscated
        assert "jane@acme.com" in full_text
        assert "(555) 222-3333" in full_text

        # SSN stays redacted
        assert "[REDACTED]" in full_text
        assert "123-45-6789" not in full_text

        # Legal citations preserved
        assert "Cal. Lab. Code § 1102.5" in full_text
        assert "Cal. Gov. Code § 12940(a)" in full_text

        # No leftover placeholders
        assert "EMAIL_1" not in full_text
        assert "PHONE_1" not in full_text

    def test_full_pipeline_complex_objection(self):
        """Full objection pipeline with multiple entity types + citations."""
        engine = _no_ner_engine()

        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [
                {
                    "ground_id": "privacy",
                    "explanation": (
                        "EMAIL_1 and PHONE_1 are private. The [REDACTED] "
                        "must be protected per Cal. Const. art. I, § 1."
                    ),
                    "strength": "high",
                },
                {
                    "ground_id": "overbroad",
                    "explanation": (
                        "The request for all records of EMAIL_1 is "
                        "overbroad under Cal. Civ. Proc. Code § 2030.060."
                    ),
                    "strength": "medium",
                },
            ],
        }])
        analyzer, mock_llm = _make_objection_analyzer(response, engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text=(
                "Produce all communications with alice@test.com, "
                "phone records for (555) 444-5555, and SSN 111-22-3333 "
                "per Cal. Civ. Proc. Code § 2031.010."
            ),
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        result = analyzer.analyze_single(req)

        # Verify obfuscation in what LLM received
        call_args = mock_llm.generate_with_tools.call_args
        user_msg = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "alice@test.com" not in user_msg
        assert "(555) 444-5555" not in user_msg
        assert "111-22-3333" not in user_msg
        assert "Cal. Civ. Proc. Code § 2031.010" in user_msg  # citation preserved

        # Verify deobfuscation in results
        assert len(result.objections) == 2

        priv = result.objections[0]
        assert "alice@test.com" in priv.explanation
        assert "(555) 444-5555" in priv.explanation
        assert "Cal. Const. art. I, § 1" in priv.explanation
        assert "[REDACTED]" in priv.explanation

        overbroad = result.objections[1]
        assert "alice@test.com" in overbroad.explanation
        assert "Cal. Civ. Proc. Code § 2030.060" in overbroad.explanation

    def test_batch_objection_shared_context_across_requests(self):
        """Batch of objection requests share one context within a chunk."""
        engine = _no_ner_engine()

        response = _mock_llm_response([
            {
                "request_number": 1,
                "applicable_objections": [{
                    "ground_id": "privacy",
                    "explanation": "EMAIL_1 is private.",
                    "strength": "medium",
                }],
            },
            {
                "request_number": 2,
                "applicable_objections": [],
                "no_objections_rationale": (
                    "The request about EMAIL_1 and PHONE_1 is proper."
                ),
            },
        ])
        analyzer, mock_llm = _make_objection_analyzer(response, engine=engine)

        requests = [
            ObjectionRequest(
                1, "Emails to alice@test.com.",
                ResponseDiscoveryType.RFPS,
            ),
            ObjectionRequest(
                2, "Phone records for (555) 666-7777 and alice@test.com.",
                ResponseDiscoveryType.RFPS,
            ),
        ]
        batch = analyzer.analyze_batch(requests)

        # Request 1: explanation deobfuscated
        assert "alice@test.com" in batch.results[0].objections[0].explanation

        # Request 2: rationale deobfuscated with both entities
        rationale = batch.results[1].no_objections_rationale
        assert "alice@test.com" in rationale
        assert "(555) 666-7777" in rationale

        # LLM saw obfuscated text
        call_args = mock_llm.generate_with_tools.call_args
        user_msg = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "alice@test.com" not in user_msg
        assert "(555) 666-7777" not in user_msg


# ── No-engine baseline ────────────────────────────────────────


class TestNoEngineBaseline:
    """Both paths work identically to pre-privacy behavior when engine=None."""

    def test_chat_no_engine_passthrough(self):
        """Chat without engine: PII passes through unchanged."""
        svc = _make_chat_svc(engine=None)
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(content="Contact: alice@test.com"),
        ]
        _setup_chat_stream(svc, "Contact alice@test.com for info.")

        full_text = _consume_chat(
            svc.generate_stream("Email alice@test.com", "case-1")
        )

        # PII passes through in both directions
        call_args = svc.llm_client.generate_stream.call_args
        user_msg = call_args.kwargs.get("user_message", "")
        assert "alice@test.com" in user_msg
        assert "alice@test.com" in full_text

    def test_objection_no_engine_passthrough(self):
        """Objection without engine: PII passes through unchanged."""
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "alice@test.com is in the request.",
                "strength": "medium",
            }],
        }])
        analyzer, mock_llm = _make_objection_analyzer(response, engine=None)

        req = ObjectionRequest(
            1, "Produce emails to alice@test.com.",
            ResponseDiscoveryType.RFPS,
        )
        result = analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_msg = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "alice@test.com" in user_msg
        assert "alice@test.com" in result.objections[0].explanation
