"""Tests for CaseChatService (L3.4/L3.5): dual-context retrieval + template.

Tests cover:
- Dual retrieval (case files + KB)
- Case notes fetching with filename resolution
- Document block building for Citations API
- System prompt generation (fallback + template)
- casefile_system.j2 template rendering (integration)
- Streaming generation (single-turn + multi-turn)
- Short follow-up query expansion
- Empty results handling
- Score conversion (distance vs relevance)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.chat import (
    CASE_TOP_K,
    KB_TOP_K,
    CaseChatService,
    CaseRetrievalResult,
)
from employee_help.retrieval.service import RetrievalResult


# ── Fixtures ────────────────────────────────────────────────────


@dataclass
class FakeEmbeddingResult:
    dense_vector: list[float]


def _make_case_chat_service(**overrides) -> CaseChatService:
    """Build a CaseChatService with mock dependencies."""
    mock_cvs = MagicMock()
    mock_embedder = MagicMock()
    mock_retrieval = MagicMock()
    mock_llm = MagicMock()
    mock_prompt_builder = MagicMock()
    mock_case_storage = MagicMock()

    # Default: embed_query returns a fake embedding
    mock_embedder.embed_query.return_value = FakeEmbeddingResult(
        dense_vector=[0.1] * 768
    )

    # Default: no search results
    mock_cvs.search_hybrid.return_value = []
    mock_retrieval.retrieve.return_value = []

    # Default: no notes
    mock_case_storage.list_notes.return_value = []

    # Default: prompt builder returns empty blocks
    mock_prompt_builder._build_document_blocks.return_value = []
    mock_prompt_builder._trim_history.return_value = []

    kwargs = {
        "case_vector_store": mock_cvs,
        "embedding_service": mock_embedder,
        "retrieval_service": mock_retrieval,
        "llm_client": mock_llm,
        "prompt_builder": mock_prompt_builder,
        "case_storage": mock_case_storage,
    }
    kwargs.update(overrides)
    return CaseChatService(**kwargs)


def _make_raw_case_result(**overrides) -> dict[str, Any]:
    """Create a raw LanceDB case result dict."""
    defaults = {
        "chunk_id": "chunk-1",
        "file_id": "file-1",
        "case_id": "case-1",
        "content": "The plaintiff was terminated on March 15.",
        "heading_path": "complaint.pdf > Page 1",
        "file_type": "pdf",
        "original_filename": "complaint.pdf",
        "_relevance_score": 0.85,
        "content_hash": "abc123",
    }
    defaults.update(overrides)
    return defaults


def _make_kb_result(**overrides) -> RetrievalResult:
    """Create a KB RetrievalResult."""
    defaults = {
        "chunk_id": 101,
        "document_id": 10,
        "source_id": 1,
        "content": "Cal. Lab. Code § 1102.5 protects whistleblowers.",
        "heading_path": "Labor Code > § 1102.5",
        "content_category": "statutory_code",
        "citation": "Cal. Lab. Code § 1102.5",
        "relevance_score": 0.9,
        "source_url": "https://leginfo.ca.gov/...",
        "content_hash": "def456",
    }
    defaults.update(overrides)
    return RetrievalResult(**defaults)


# ── TestCaseRetrievalResult ─────────────────────────────────────


class TestCaseRetrievalResult:
    def test_dataclass_fields(self):
        r = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="text",
            heading_path="file.pdf > Page 1",
            file_type="pdf",
            original_filename="file.pdf",
            relevance_score=0.9,
        )
        assert r.chunk_id == "c1"
        assert r.content_hash == ""  # default

    def test_content_hash_optional(self):
        r = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="text",
            heading_path="",
            file_type="pdf",
            original_filename="f.pdf",
            relevance_score=0.5,
            content_hash="hash123",
        )
        assert r.content_hash == "hash123"


# ── TestRetrieveForCase ─────────────────────────────────────────


class TestRetrieveForCase:
    def test_embeds_query_once(self):
        svc = _make_case_chat_service()
        svc.retrieve_for_case("termination question", "case-1")

        # embed_query called exactly once (reused for both searches)
        svc.embedding_service.embed_query.assert_called_once_with(
            "termination question"
        )

    def test_searches_case_vector_store(self):
        svc = _make_case_chat_service()
        svc.retrieve_for_case("query", "case-1")

        svc.case_vector_store.search_hybrid.assert_called_once_with(
            case_id="case-1",
            query_text="query",
            query_vector=[0.1] * 768,
            top_k=CASE_TOP_K,
        )

    def test_searches_kb_in_attorney_mode(self):
        svc = _make_case_chat_service()
        svc.retrieve_for_case("query", "case-1")

        svc.retrieval_service.retrieve.assert_called_once_with(
            query="query",
            mode="attorney",
            top_k=KB_TOP_K,
        )

    def test_custom_top_k(self):
        svc = _make_case_chat_service(case_top_k=20, kb_top_k=8)
        svc.retrieve_for_case("query", "case-1")

        svc.case_vector_store.search_hybrid.assert_called_once_with(
            case_id="case-1",
            query_text="query",
            query_vector=[0.1] * 768,
            top_k=20,
        )
        svc.retrieval_service.retrieve.assert_called_once_with(
            query="query",
            mode="attorney",
            top_k=8,
        )

    def test_returns_both_result_types(self):
        svc = _make_case_chat_service()
        raw = [_make_raw_case_result()]
        kb = [_make_kb_result()]
        svc.case_vector_store.search_hybrid.return_value = raw
        svc.retrieval_service.retrieve.return_value = kb

        case_results, kb_results = svc.retrieve_for_case("query", "case-1")

        assert len(case_results) == 1
        assert isinstance(case_results[0], CaseRetrievalResult)
        assert len(kb_results) == 1
        assert isinstance(kb_results[0], RetrievalResult)

    def test_empty_case_results(self):
        svc = _make_case_chat_service()
        kb = [_make_kb_result()]
        svc.retrieval_service.retrieve.return_value = kb

        case_results, kb_results = svc.retrieve_for_case("query", "case-1")

        assert case_results == []
        assert len(kb_results) == 1

    def test_empty_kb_results(self):
        svc = _make_case_chat_service()
        raw = [_make_raw_case_result()]
        svc.case_vector_store.search_hybrid.return_value = raw

        case_results, kb_results = svc.retrieve_for_case("query", "case-1")

        assert len(case_results) == 1
        assert kb_results == []

    def test_both_empty(self):
        svc = _make_case_chat_service()
        case_results, kb_results = svc.retrieve_for_case("query", "case-1")

        assert case_results == []
        assert kb_results == []


# ── TestToCaseResults ──────────────────────────────────────────


class TestToCaseResults:
    def test_relevance_score_extraction(self):
        svc = _make_case_chat_service()
        raw = [_make_raw_case_result(_relevance_score=0.92)]
        results = svc._to_case_results(raw)

        assert results[0].relevance_score == pytest.approx(0.92)

    def test_distance_to_similarity_conversion(self):
        svc = _make_case_chat_service()
        raw = [{"_distance": 0.3, "chunk_id": "c1", "content": "text"}]
        results = svc._to_case_results(raw)

        assert results[0].relevance_score == pytest.approx(0.7)

    def test_relevance_takes_precedence_over_distance(self):
        svc = _make_case_chat_service()
        raw = [
            {
                "_relevance_score": 0.85,
                "_distance": 0.3,
                "chunk_id": "c1",
                "content": "text",
            }
        ]
        results = svc._to_case_results(raw)

        assert results[0].relevance_score == pytest.approx(0.85)

    def test_no_score_defaults_to_zero(self):
        svc = _make_case_chat_service()
        raw = [{"chunk_id": "c1", "content": "text"}]
        results = svc._to_case_results(raw)

        assert results[0].relevance_score == 0.0

    def test_negative_distance_clamped(self):
        svc = _make_case_chat_service()
        raw = [{"_distance": 1.5, "chunk_id": "c1", "content": "text"}]
        results = svc._to_case_results(raw)

        assert results[0].relevance_score == 0.0

    def test_all_fields_mapped(self):
        svc = _make_case_chat_service()
        raw = [_make_raw_case_result()]
        results = svc._to_case_results(raw)

        r = results[0]
        assert r.chunk_id == "chunk-1"
        assert r.file_id == "file-1"
        assert r.case_id == "case-1"
        assert r.content == "The plaintiff was terminated on March 15."
        assert r.heading_path == "complaint.pdf > Page 1"
        assert r.file_type == "pdf"
        assert r.original_filename == "complaint.pdf"
        assert r.content_hash == "abc123"

    def test_missing_fields_default(self):
        svc = _make_case_chat_service()
        raw = [{"_relevance_score": 0.5}]
        results = svc._to_case_results(raw)

        r = results[0]
        assert r.chunk_id == ""
        assert r.file_id == ""
        assert r.content == ""
        assert r.original_filename == ""


# ── TestGetCaseNotes ────────────────────────────────────────────


class TestGetCaseNotes:
    def test_no_notes(self):
        svc = _make_case_chat_service()
        result = svc.get_case_notes("case-1")
        assert result == []

    def test_general_note(self):
        svc = _make_case_chat_service()
        note = MagicMock(content="Important context", file_id=None)
        svc.case_storage.list_notes.return_value = [note]

        result = svc.get_case_notes("case-1")

        assert len(result) == 1
        assert result[0]["content"] == "Important context"
        assert result[0]["file_id"] is None
        assert result[0]["filename"] is None

    def test_file_linked_note_resolves_filename(self):
        svc = _make_case_chat_service()
        note = MagicMock(content="OCR looks bad", file_id="file-1")
        svc.case_storage.list_notes.return_value = [note]
        cf = MagicMock(original_filename="scan.pdf")
        svc.case_storage.get_case_file.return_value = cf

        result = svc.get_case_notes("case-1")

        assert result[0]["filename"] == "scan.pdf"
        svc.case_storage.get_case_file.assert_called_once_with("file-1")

    def test_file_linked_note_missing_file(self):
        svc = _make_case_chat_service()
        note = MagicMock(content="Note", file_id="deleted-file")
        svc.case_storage.list_notes.return_value = [note]
        svc.case_storage.get_case_file.return_value = None

        result = svc.get_case_notes("case-1")

        assert result[0]["filename"] is None

    def test_multiple_notes(self):
        svc = _make_case_chat_service()
        n1 = MagicMock(content="Note 1", file_id=None)
        n2 = MagicMock(content="Note 2", file_id="f1")
        svc.case_storage.list_notes.return_value = [n1, n2]
        svc.case_storage.get_case_file.return_value = MagicMock(
            original_filename="doc.pdf"
        )

        result = svc.get_case_notes("case-1")

        assert len(result) == 2


# ── TestBuildCaseDocumentBlocks ─────────────────────────────────


class TestBuildCaseDocumentBlocks:
    def test_case_file_blocks_come_first(self):
        svc = _make_case_chat_service()
        case_results = [
            CaseRetrievalResult(
                chunk_id="c1",
                file_id="f1",
                case_id="case-1",
                content="Case content",
                heading_path="file.pdf > Page 1",
                file_type="pdf",
                original_filename="file.pdf",
                relevance_score=0.9,
            )
        ]
        kb_results = [_make_kb_result()]
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": "KB doc"}
        ]

        blocks, context = svc.build_case_document_blocks(
            case_results, kb_results
        )

        assert len(blocks) == 2
        # First block is case file
        assert "Case File" in blocks[0]["source"]["content"][0]["text"]
        # Second block is KB
        assert blocks[1]["title"] == "KB doc"

    def test_case_block_title_with_heading(self):
        svc = _make_case_chat_service()
        cr = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case-1",
            content="text",
            heading_path="Page 3",
            file_type="pdf",
            original_filename="report.pdf",
            relevance_score=0.8,
        )

        blocks, _ = svc.build_case_document_blocks([cr], [])

        assert blocks[0]["title"] == "report.pdf — Page 3"

    def test_case_block_title_without_heading(self):
        svc = _make_case_chat_service()
        cr = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case-1",
            content="text",
            heading_path="",
            file_type="docx",
            original_filename="memo.docx",
            relevance_score=0.8,
        )

        blocks, _ = svc.build_case_document_blocks([cr], [])

        assert blocks[0]["title"] == "memo.docx"

    def test_context_order_preserved(self):
        svc = _make_case_chat_service()
        cr = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case-1",
            content="case text",
            heading_path="",
            file_type="pdf",
            original_filename="f.pdf",
            relevance_score=0.9,
        )
        kb = _make_kb_result()
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": "KB"}
        ]

        _, context = svc.build_case_document_blocks([cr], [kb])

        assert len(context) == 2
        assert isinstance(context[0], CaseRetrievalResult)
        assert isinstance(context[1], RetrievalResult)

    def test_citations_enabled_on_case_blocks(self):
        svc = _make_case_chat_service()
        cr = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case-1",
            content="text",
            heading_path="",
            file_type="pdf",
            original_filename="f.pdf",
            relevance_score=0.8,
        )

        blocks, _ = svc.build_case_document_blocks([cr], [])

        assert blocks[0]["citations"] == {"enabled": True}

    def test_empty_inputs(self):
        svc = _make_case_chat_service()
        blocks, context = svc.build_case_document_blocks([], [])

        assert blocks == []
        assert context == []

    def test_metadata_in_case_block_content(self):
        svc = _make_case_chat_service()
        cr = CaseRetrievalResult(
            chunk_id="c1",
            file_id="f1",
            case_id="case-1",
            content="Deposition of Jane Doe",
            heading_path="",
            file_type="docx",
            original_filename="deposition.docx",
            relevance_score=0.8,
        )

        blocks, _ = svc.build_case_document_blocks([cr], [])

        text = blocks[0]["source"]["content"][0]["text"]
        assert "[Case File | deposition.docx | Type: docx]" in text
        assert "Deposition of Jane Doe" in text


# ── TestBuildCaseSystemPrompt ──────────────────────────────────


class TestBuildCaseSystemPrompt:
    def test_fallback_prompt_without_notes(self):
        svc = _make_case_chat_service()
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        prompt = svc.build_case_system_prompt([])

        assert "LITIGAGENT" in prompt
        assert "Case Files" in prompt
        assert "Legal Research" in prompt
        assert "Attorney Notes" not in prompt

    def test_fallback_prompt_with_general_note(self):
        svc = _make_case_chat_service()
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        notes = [{"content": "Key witness is Smith", "filename": None}]
        prompt = svc.build_case_system_prompt(notes)

        assert "Attorney Notes" in prompt
        assert "[General Case Note]" in prompt
        assert "Key witness is Smith" in prompt

    def test_fallback_prompt_with_file_note(self):
        svc = _make_case_chat_service()
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        notes = [{"content": "Bad OCR", "filename": "scan.pdf"}]
        prompt = svc.build_case_system_prompt(notes)

        assert "[Note for: scan.pdf]" in prompt
        assert "Bad OCR" in prompt

    def test_uses_template_when_available(self):
        svc = _make_case_chat_service()
        svc.prompt_builder._load_template.return_value = (
            "You are LITIGAGENT.{% for n in case_notes %}{{ n.content }}{% endfor %}"
        )
        svc.prompt_builder._render_template.return_value = (
            "You are LITIGAGENT.Important note"
        )

        notes = [{"content": "Important note", "filename": None}]
        prompt = svc.build_case_system_prompt(notes)

        assert prompt == "You are LITIGAGENT.Important note"
        svc.prompt_builder._render_template.assert_called_once()

    def test_fallback_includes_instructions(self):
        svc = _make_case_chat_service()
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        prompt = svc.build_case_system_prompt([])

        assert "citing case files" in prompt
        assert "statutory citations" in prompt
        assert "does not constitute legal advice" in prompt


# ── TestGenerateStream ──────────────────────────────────────────


class TestGenerateStream:
    def test_empty_results_yields_fallback(self):
        svc = _make_case_chat_service()

        stream, case_r, kb_r, meta = svc.generate_stream("query", "case-1")
        text = "".join(stream)

        assert "couldn't find relevant information" in text
        assert case_r == []
        assert kb_r == []
        assert meta == []

    def test_calls_llm_with_document_blocks(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        # Mock LLM stream
        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream.return_value = iter([
            StreamChunk(text="Answer here."),
            StreamChunk(
                text="",
                is_final=True,
                citations=[],
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-6",
            ),
        ])

        stream, case_r, kb_r, meta = svc.generate_stream("query", "case-1")
        text = "".join(stream)

        assert text == "Answer here."
        assert len(case_r) == 1
        assert len(meta) == 1
        assert meta[0]["model"] == "claude-sonnet-4-6"

        # Verify LLM called in attorney mode
        call_kwargs = svc.llm_client.generate_stream.call_args
        assert call_kwargs.kwargs["mode"] == "attorney"
        assert call_kwargs.kwargs["document_blocks"] is not None

    def test_includes_notes_in_context(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        note = MagicMock(content="Plaintiff is credible", file_id=None)
        svc.case_storage.list_notes.return_value = [note]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream.return_value = iter([
            StreamChunk(text="ok", is_final=True, citations=[]),
        ])

        stream, _, _, _ = svc.generate_stream("query", "case-1")
        list(stream)  # consume

        # System prompt should contain notes
        call_args = svc.llm_client.generate_stream.call_args
        system_prompt = call_args.kwargs["system_prompt"]
        assert "Plaintiff is credible" in system_prompt

    def test_streams_with_only_kb_results(self):
        svc = _make_case_chat_service()
        svc.retrieval_service.retrieve.return_value = [_make_kb_result()]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": "KB"}
        ]

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream.return_value = iter([
            StreamChunk(text="Legal answer", is_final=True, citations=[]),
        ])

        stream, case_r, kb_r, _ = svc.generate_stream("query", "case-1")
        text = "".join(stream)

        assert text == "Legal answer"
        assert case_r == []
        assert len(kb_r) == 1


# ── TestGenerateStreamMultiturn ─────────────────────────────────


class TestGenerateStreamMultiturn:
    def test_expands_short_followup(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            StreamChunk(text="Response", is_final=True, citations=[]),
        ])

        history = [
            {"role": "user", "content": "What about retaliation claims?"},
            {"role": "assistant", "content": "Retaliation is..."},
        ]

        stream, _, _, _ = svc.generate_stream_multiturn(
            query="more details",
            case_id="case-1",
            conversation_history=history,
            turn_number=2,
        )
        list(stream)  # consume

        # Should have searched with expanded query
        call_args = svc.case_vector_store.search_hybrid.call_args
        assert "retaliation" in call_args.kwargs["query_text"].lower()
        assert "more details" in call_args.kwargs["query_text"]

    def test_no_expansion_for_long_query(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            StreamChunk(text="Response", is_final=True, citations=[]),
        ])

        long_query = "What are the specific elements of a retaliation claim under FEHA?"
        stream, _, _, _ = svc.generate_stream_multiturn(
            query=long_query,
            case_id="case-1",
            conversation_history=[
                {"role": "user", "content": "Original question"},
            ],
            turn_number=2,
        )
        list(stream)

        # Long query should not be expanded
        call_args = svc.case_vector_store.search_hybrid.call_args
        assert call_args.kwargs["query_text"] == long_query

    def test_no_expansion_on_first_turn(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            StreamChunk(text="Response", is_final=True, citations=[]),
        ])

        stream, _, _, _ = svc.generate_stream_multiturn(
            query="short",
            case_id="case-1",
            turn_number=1,
        )
        list(stream)

        call_args = svc.case_vector_store.search_hybrid.call_args
        assert call_args.kwargs["query_text"] == "short"

    def test_empty_results_multiturn(self):
        svc = _make_case_chat_service()

        stream, case_r, kb_r, meta = svc.generate_stream_multiturn(
            "query", "case-1"
        )
        text = "".join(stream)

        assert "couldn't find" in text
        assert case_r == []
        assert kb_r == []

    def test_builds_multiturn_messages(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError
        svc.prompt_builder._trim_history.return_value = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            StreamChunk(text="Multi-turn answer", is_final=True, citations=[]),
        ])

        stream, _, _, _ = svc.generate_stream_multiturn(
            query="Follow-up question here",
            case_id="case-1",
            conversation_history=[
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
            ],
            turn_number=2,
        )
        text = "".join(stream)

        assert text == "Multi-turn answer"

        # Verify messages structure
        call_args = svc.llm_client.generate_stream_multiturn.call_args
        messages = call_args.kwargs["messages"]
        # History (2 turns) + current turn with doc blocks
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        # Last message content should be a list (doc blocks + text)
        assert isinstance(messages[2]["content"], list)

    def test_stream_metadata_populated(self):
        svc = _make_case_chat_service()
        svc.case_vector_store.search_hybrid.return_value = [
            _make_raw_case_result()
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        from employee_help.generation.llm import StreamChunk

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            StreamChunk(text="text"),
            StreamChunk(
                text="",
                is_final=True,
                citations=[{"doc_index": 0}],
                input_tokens=200,
                output_tokens=100,
                model="claude-sonnet-4-6",
            ),
        ])

        stream, _, _, meta = svc.generate_stream_multiturn(
            "query", "case-1", turn_number=1
        )
        list(stream)  # consume

        assert len(meta) == 1
        assert meta[0]["input_tokens"] == 200
        assert meta[0]["output_tokens"] == 100
        assert meta[0]["model"] == "claude-sonnet-4-6"


# ── TestCasefileSystemTemplate ──────────────────────────────────


class TestCasefileSystemTemplate:
    """Integration tests: render the real casefile_system.j2 template."""

    @pytest.fixture()
    def prompt_builder(self):
        from employee_help.generation.prompts import PromptBuilder

        return PromptBuilder(prompts_dir="config/prompts")

    def test_template_loads(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        assert "LITIGAGENT" in text

    def test_render_without_notes(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        rendered = prompt_builder._render_template(text, case_notes=[])

        assert "LITIGAGENT" in rendered
        assert "Case Files" in rendered
        assert "Legal Research" in rendered
        assert "does not constitute legal advice" in rendered
        # No notes section when empty
        assert "Attorney Notes" not in rendered

    def test_render_with_general_note(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        notes = [{"content": "Key witness is John Smith", "filename": None, "file_id": None}]
        rendered = prompt_builder._render_template(text, case_notes=notes)

        assert "Attorney Notes" in rendered
        assert "[General Case Note]" in rendered
        assert "Key witness is John Smith" in rendered

    def test_render_with_file_note(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        notes = [{"content": "OCR quality is poor", "filename": "scan.pdf", "file_id": "f1"}]
        rendered = prompt_builder._render_template(text, case_notes=notes)

        assert "[Note for: scan.pdf]" in rendered
        assert "OCR quality is poor" in rendered

    def test_render_with_multiple_notes(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        notes = [
            {"content": "Plaintiff was terminated", "filename": None, "file_id": None},
            {"content": "See page 3", "filename": "complaint.pdf", "file_id": "f1"},
            {"content": "Contract is ambiguous", "filename": "contract.docx", "file_id": "f2"},
        ]
        rendered = prompt_builder._render_template(text, case_notes=notes)

        assert "[General Case Note]" in rendered
        assert "Plaintiff was terminated" in rendered
        assert "[Note for: complaint.pdf]" in rendered
        assert "[Note for: contract.docx]" in rendered

    def test_template_contains_citation_guidance(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        rendered = prompt_builder._render_template(text, case_notes=[])

        assert "Citation Format" in rendered
        assert "Cal. Lab. Code" in rendered
        assert "Only cite" in rendered

    def test_template_contains_analysis_framework(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        rendered = prompt_builder._render_template(text, case_notes=[])

        assert "Analysis Framework" in rendered
        assert "facts" in rendered.lower()
        assert "legal analysis" in rendered.lower()

    def test_template_contains_work_product_section(self, prompt_builder):
        text = prompt_builder._load_template("casefile_system.j2")
        rendered = prompt_builder._render_template(text, case_notes=[])

        assert "Work Product" in rendered
        assert "factual foundation" in rendered

    def test_attorney_notes_conditional_instruction(self, prompt_builder):
        """When notes are present, the analysis framework should mention them."""
        text = prompt_builder._load_template("casefile_system.j2")

        # Without notes: no mention of attorney's notes in analysis
        rendered_no_notes = prompt_builder._render_template(text, case_notes=[])
        assert "professional judgment" not in rendered_no_notes

        # With notes: mentions attorney's professional judgment
        rendered_with_notes = prompt_builder._render_template(
            text,
            case_notes=[{"content": "Note", "filename": None, "file_id": None}],
        )
        assert "professional judgment" in rendered_with_notes

    def test_end_to_end_with_case_chat_service(self, prompt_builder):
        """CaseChatService.build_case_system_prompt uses the real template."""
        svc = _make_case_chat_service()
        svc.prompt_builder = prompt_builder

        notes = [
            {"content": "Key evidence on page 5", "filename": "exhibit_a.pdf", "file_id": "f1"},
        ]
        prompt = svc.build_case_system_prompt(notes)

        assert "LITIGAGENT" in prompt
        assert "[Note for: exhibit_a.pdf]" in prompt
        assert "Key evidence on page 5" in prompt
        assert "does not constitute legal advice" in prompt
