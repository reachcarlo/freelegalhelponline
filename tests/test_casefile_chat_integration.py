"""Integration tests for LITIGAGENT chat pipeline (L3.11).

Covers the gaps identified across L3.1–L3.10 unit tests:
- Citation linking: source event fields, persistence round-trip
- Dual-context retrieval: mixed results ordering, deduplication
- Prompt construction: full pipeline (notes + doc blocks + system prompt)
- Error resilience: partial retrieval failure, stream-level errors
- Multi-turn integration: fresh retrieval per turn, query expansion
"""

from __future__ import annotations

import json
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
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseChatSession,
    CaseChatTurn,
)


# ── Fixtures ────────────────────────────────────────────────────


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


@dataclass
class FakeUser:
    sub: str = "test-user"
    org: str = "test-org"
    email: str = "test@example.com"
    role: str = "admin"


def _make_svc(**overrides) -> CaseChatService:
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


def _raw_case(
    chunk_id: str = "chunk-1",
    file_id: str = "file-1",
    case_id: str = "case-1",
    filename: str = "complaint.pdf",
    file_type: str = "pdf",
    heading: str = "complaint.pdf > Page 1",
    score: float = 0.85,
    content: str = "Plaintiff was terminated on March 15.",
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


@pytest.fixture()
def db():
    import sqlite3 as _sqlite3
    from employee_help.storage.storage import _SCHEMA

    conn = _sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    yield conn
    conn.close()


@pytest.fixture()
def case_storage(db):
    return CaseStorage(conn=db)


@pytest.fixture()
def sample_case(case_storage):
    case = Case(
        name="Integration Test Case",
        user_id="test-user",
        organization_id="test-org",
    )
    return case_storage.create_case(case)


# ── Citation linking ────────────────────────────────────────────


class TestCitationLinking:
    """Verify source events carry the correct fields for file→chunk mapping."""

    def test_case_source_carries_file_id_and_chunk_id(self):
        """CaseRetrievalResult preserves file_id and chunk_id for linking."""
        svc = _make_svc()
        raw = [_raw_case(chunk_id="c-42", file_id="f-7")]
        svc.case_vector_store.search_hybrid.return_value = raw

        case_results, _ = svc.retrieve_for_case("query", "case-1")

        assert case_results[0].file_id == "f-7"
        assert case_results[0].chunk_id == "c-42"

    def test_multiple_chunks_same_file_produce_separate_results(self):
        """Two chunks from the same file should produce two results."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(chunk_id="c-1", file_id="f-1", heading="Page 1"),
            _raw_case(chunk_id="c-2", file_id="f-1", heading="Page 2"),
        ]

        case_results, _ = svc.retrieve_for_case("query", "case-1")

        assert len(case_results) == 2
        assert case_results[0].chunk_id == "c-1"
        assert case_results[1].chunk_id == "c-2"
        assert all(r.file_id == "f-1" for r in case_results)

    def test_mixed_file_types_in_case_results(self):
        """PDF, DOCX, EML chunks all appear with correct file_type."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(chunk_id="c-1", file_id="f-1", file_type="pdf", filename="complaint.pdf"),
            _raw_case(chunk_id="c-2", file_id="f-2", file_type="docx", filename="contract.docx"),
            _raw_case(chunk_id="c-3", file_id="f-3", file_type="eml", filename="notice.eml"),
        ]

        case_results, _ = svc.retrieve_for_case("query", "case-1")

        types = [r.file_type for r in case_results]
        assert types == ["pdf", "docx", "eml"]

    def test_case_blocks_include_file_metadata_for_citation_display(self):
        """Document blocks should include filename and file type in metadata header."""
        svc = _make_svc()
        cr = CaseRetrievalResult(
            chunk_id="c-1",
            file_id="f-1",
            case_id="case-1",
            content="Deposition testimony about events on March 15.",
            heading_path="Page 5",
            file_type="pdf",
            original_filename="deposition.pdf",
            relevance_score=0.9,
        )

        blocks, context = svc.build_case_document_blocks([cr], [])

        assert len(blocks) == 1
        text = blocks[0]["source"]["content"][0]["text"]
        assert "[Case File | deposition.pdf | Type: pdf]" in text
        assert "Deposition testimony" in text
        assert blocks[0]["title"] == "deposition.pdf — Page 5"

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_source_event_fields_complete(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """SSE sources event includes file_id, chunk_id, heading_path."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat = MagicMock()

        def fake_stream(query, case_id, **kwargs):
            metadata: list[dict] = []

            def gen():
                yield "Answer."
                metadata.append({
                    "citations": [],
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "model": "claude-sonnet-4-6",
                })

            case_results = [
                MagicMock(
                    original_filename="contract.docx",
                    relevance_score=0.88,
                    file_id="f-77",
                    chunk_id="c-42",
                    heading_path="Section 3",
                ),
            ]
            kb_results = [
                MagicMock(
                    heading_path="Labor Code > § 2802",
                    relevance_score=0.82,
                    chunk_id="kb-55",
                    content_category="statutory_code",
                    citation="Cal. Lab. Code § 2802",
                ),
            ]
            return gen(), case_results, kb_results, metadata

        mock_chat.generate_stream.side_effect = fake_stream
        mock_chat_fn.return_value = mock_chat

        from employee_help.api.casefile_routes import case_chat
        from employee_help.api.casefile_schemas import CaseChatRequest

        body = CaseChatRequest(query="What are my obligations?")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)

        events = []
        async for chunk in response.body_iterator:
            for line in chunk.split("\n"):
                if line.startswith("event: "):
                    evt_type = line[7:]
                elif line.startswith("data: ") and evt_type:
                    events.append({"event": evt_type, "data": json.loads(line[6:])})
                    evt_type = None

        sources = next(e["data"] for e in events if e["event"] == "sources")

        # Case source fields
        cs = sources["case_sources"][0]
        assert cs["source_type"] == "case_file"
        assert cs["file_id"] == "f-77"
        assert cs["chunk_id"] == "c-42"
        assert cs["heading_path"] == "Section 3"
        assert cs["title"] == "contract.docx"
        assert cs["relevance_score"] == pytest.approx(0.88)

        # KB source fields
        kb = sources["kb_sources"][0]
        assert kb["source_type"] == "knowledge_base"
        assert kb["chunk_id"] == "kb-55"
        assert kb["content_category"] == "statutory_code"
        assert kb["heading_path"] == "Labor Code > § 2802"


# ── Source persistence round-trip ───────────────────────────────


class TestSourcePersistence:
    """Verify sources survive the chat→persist→retrieve cycle."""

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_sources_persisted_in_assistant_turn(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """Assistant turn should have sources JSON with file_ids and chunk_ids."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat = MagicMock()

        def fake_stream(query, case_id, **kwargs):
            metadata: list[dict] = []

            def gen():
                yield "Analysis text."
                metadata.append({
                    "citations": [],
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "model": "claude-sonnet-4-6",
                })

            case_results = [
                MagicMock(
                    original_filename="complaint.pdf",
                    relevance_score=0.9,
                    file_id="f-1",
                    chunk_id="c-1",
                    heading_path="Page 1",
                ),
                MagicMock(
                    original_filename="contract.docx",
                    relevance_score=0.85,
                    file_id="f-2",
                    chunk_id="c-2",
                    heading_path="Section 5",
                ),
            ]
            kb_results = [
                MagicMock(
                    heading_path="Labor Code > § 1102.5",
                    relevance_score=0.8,
                    chunk_id="kb-1",
                    content_category="statutory_code",
                    citation="Cal. Lab. Code § 1102.5",
                ),
            ]
            return gen(), case_results, kb_results, metadata

        mock_chat.generate_stream.side_effect = fake_stream
        mock_chat_fn.return_value = mock_chat

        from employee_help.api.casefile_routes import case_chat
        from employee_help.api.casefile_schemas import CaseChatRequest

        body = CaseChatRequest(query="Analyze the case")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)

        # Consume the SSE stream to trigger persistence
        session_id = None
        async for chunk in response.body_iterator:
            for line in chunk.split("\n"):
                if line.startswith("data: ") and "session_id" in line:
                    data = json.loads(line[6:])
                    if "session_id" in data:
                        session_id = data["session_id"]

        assert session_id is not None

        # Verify persisted turns
        turns = case_storage.list_chat_turns(session_id)
        assert len(turns) == 2  # user + assistant

        assistant_turn = turns[1]
        assert assistant_turn.role == "assistant"
        assert assistant_turn.content == "Analysis text."
        assert assistant_turn.sources is not None

        sources = json.loads(assistant_turn.sources)
        assert len(sources["case_sources"]) == 2
        assert sources["case_sources"][0]["file_id"] == "f-1"
        assert sources["case_sources"][0]["filename"] == "complaint.pdf"
        assert sources["case_sources"][1]["file_id"] == "f-2"
        assert len(sources["kb_sources"]) == 1
        assert sources["kb_sources"][0]["chunk_id"] == "kb-1"
        assert sources["kb_sources"][0]["heading"] == "Labor Code > § 1102.5"

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_sources_round_trip_via_history_endpoint(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        """Sources persist in DB and are returned via the history endpoint."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        # Manually create session with turns including sources
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="What about retaliation?",
        ))
        sources_data = {
            "case_sources": [
                {"file_id": "f-1", "filename": "complaint.pdf"},
                {"file_id": "f-2", "filename": "hr-email.eml"},
            ],
            "kb_sources": [
                {"chunk_id": "kb-42", "heading": "Gov Code > § 12940"},
            ],
        }
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="assistant",
            content="Retaliation claims under FEHA...",
            sources=json.dumps(sources_data),
        ))

        from employee_help.api.casefile_routes import get_chat_history

        request = MagicMock()
        result = await get_chat_history(
            sample_case.id, session.id, request
        )

        assert len(result.turns) == 2
        assistant = result.turns[1]
        assert assistant.sources is not None

        # The sources field should be the parsed JSON
        parsed = (
            json.loads(assistant.sources)
            if isinstance(assistant.sources, str)
            else assistant.sources
        )
        assert len(parsed["case_sources"]) == 2
        assert parsed["case_sources"][0]["file_id"] == "f-1"
        assert parsed["kb_sources"][0]["chunk_id"] == "kb-42"


# ── Dual-context document block ordering ────────────────────────


class TestDualContextBlocks:
    """Document blocks are ordered: case files first, then KB."""

    def test_multiple_case_files_then_multiple_kb(self):
        """3 case results + 2 KB results → blocks ordered correctly."""
        svc = _make_svc()

        case_results = [
            CaseRetrievalResult(
                chunk_id=f"c-{i}",
                file_id=f"f-{i}",
                case_id="case-1",
                content=f"Case content {i}",
                heading_path=f"Page {i}",
                file_type="pdf",
                original_filename=f"doc{i}.pdf",
                relevance_score=0.9 - i * 0.05,
            )
            for i in range(3)
        ]
        kb_results = [
            _kb_result(chunk_id=200 + i, heading=f"Statute § {i}")
            for i in range(2)
        ]

        # KB blocks returned by prompt builder
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": f"KB {i}"}
            for i in range(2)
        ]

        blocks, context = svc.build_case_document_blocks(
            case_results, kb_results
        )

        assert len(blocks) == 5
        # First 3 are case file blocks
        for i in range(3):
            assert "Case File" in blocks[i]["source"]["content"][0]["text"]
            assert blocks[i]["citations"] == {"enabled": True}
        # Last 2 are KB blocks
        assert blocks[3]["title"] == "KB 0"
        assert blocks[4]["title"] == "KB 1"

        # Context order matches
        assert len(context) == 5
        for i in range(3):
            assert isinstance(context[i], CaseRetrievalResult)
        for i in range(3, 5):
            assert isinstance(context[i], RetrievalResult)

    def test_only_case_results(self):
        """No KB results → only case file blocks."""
        svc = _make_svc()
        cr = CaseRetrievalResult(
            chunk_id="c-1",
            file_id="f-1",
            case_id="case-1",
            content="Only case text",
            heading_path="",
            file_type="txt",
            original_filename="notes.txt",
            relevance_score=0.8,
        )

        blocks, context = svc.build_case_document_blocks([cr], [])

        assert len(blocks) == 1
        assert "Case File" in blocks[0]["source"]["content"][0]["text"]
        assert context == [cr]

    def test_only_kb_results(self):
        """No case results → only KB blocks from PromptBuilder."""
        svc = _make_svc()
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": "Statute"}
        ]

        blocks, context = svc.build_case_document_blocks(
            [], [_kb_result()]
        )

        assert len(blocks) == 1
        assert blocks[0]["title"] == "Statute"

    def test_case_block_title_format(self):
        """Case block titles: 'filename — heading' when heading exists."""
        svc = _make_svc()

        with_heading = CaseRetrievalResult(
            chunk_id="c-1", file_id="f-1", case_id="case-1",
            content="text", heading_path="Page 3",
            file_type="pdf", original_filename="report.pdf",
            relevance_score=0.8,
        )
        without_heading = CaseRetrievalResult(
            chunk_id="c-2", file_id="f-2", case_id="case-1",
            content="text", heading_path="",
            file_type="docx", original_filename="memo.docx",
            relevance_score=0.7,
        )

        blocks, _ = svc.build_case_document_blocks(
            [with_heading, without_heading], []
        )

        assert blocks[0]["title"] == "report.pdf — Page 3"
        assert blocks[1]["title"] == "memo.docx"


# ── Full prompt construction pipeline ───────────────────────────


class TestPromptPipeline:
    """Test notes + system prompt + document blocks assembled together."""

    def test_notes_in_system_prompt_not_in_document_blocks(self):
        """Notes appear in system prompt only, not duplicated in doc blocks."""
        svc = _make_svc()
        note = MagicMock(content="Key witness is Smith", file_id=None)
        svc.case_storage.list_notes.return_value = [note]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        notes = svc.get_case_notes("case-1")
        system_prompt = svc.build_case_system_prompt(notes)

        cr = CaseRetrievalResult(
            chunk_id="c-1", file_id="f-1", case_id="case-1",
            content="Complaint text", heading_path="Page 1",
            file_type="pdf", original_filename="complaint.pdf",
            relevance_score=0.9,
        )
        blocks, _ = svc.build_case_document_blocks([cr], [])

        # Notes in system prompt
        assert "Key witness is Smith" in system_prompt
        # Notes NOT in document blocks
        block_text = blocks[0]["source"]["content"][0]["text"]
        assert "Key witness" not in block_text

    def test_full_pipeline_assembles_all_components(self):
        """Retrieve → notes → system prompt → doc blocks → LLM call."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(chunk_id="c-1", file_id="f-1")
        ]
        svc.retrieval_service.retrieve.return_value = [_kb_result()]
        svc.prompt_builder._build_document_blocks.return_value = [
            {"type": "document", "title": "KB statute"}
        ]

        note = MagicMock(content="Defendant is ABC Corp", file_id=None)
        svc.case_storage.list_notes.return_value = [note]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        svc.llm_client.generate_stream.return_value = iter([
            FakeStreamChunk(text="Combined answer."),
            FakeStreamChunk(
                text="", is_final=True, citations=[],
                input_tokens=300, output_tokens=150,
                model="claude-sonnet-4-6",
            ),
        ])

        stream, case_r, kb_r, meta = svc.generate_stream("query", "case-1")
        text = "".join(stream)

        assert text == "Combined answer."
        assert len(case_r) == 1
        assert len(kb_r) == 1
        assert len(meta) == 1

        # Verify LLM received system prompt with notes
        call_kwargs = svc.llm_client.generate_stream.call_args.kwargs
        assert "Defendant is ABC Corp" in call_kwargs["system_prompt"]
        assert call_kwargs["mode"] == "attorney"

        # Verify document blocks were passed
        doc_blocks = call_kwargs["document_blocks"]
        assert len(doc_blocks) == 2  # 1 case + 1 KB
        assert "Case File" in doc_blocks[0]["source"]["content"][0]["text"]

    def test_template_renders_with_file_note(self):
        """Integration: real template + file-linked note → correct output."""
        from employee_help.generation.prompts import PromptBuilder

        pb = PromptBuilder(prompts_dir="config/prompts")
        svc = _make_svc(prompt_builder=pb)

        # Mock note with file linkage
        note = MagicMock(content="OCR on page 5 is unreliable", file_id="f-3")
        svc.case_storage.list_notes.return_value = [note]
        svc.case_storage.get_case_file.return_value = MagicMock(
            original_filename="scan.pdf"
        )

        notes = svc.get_case_notes("case-1")
        prompt = svc.build_case_system_prompt(notes)

        assert "LITIGAGENT" in prompt
        assert "[Note for: scan.pdf]" in prompt
        assert "OCR on page 5 is unreliable" in prompt
        assert "does not constitute legal advice" in prompt


# ── Error resilience ────────────────────────────────────────────


class TestErrorResilience:
    """Test behavior when parts of the pipeline fail."""

    def test_kb_retrieval_error_propagates(self):
        """If KB retrieval raises, the error propagates (no silent swallowing)."""
        svc = _make_svc()
        svc.retrieval_service.retrieve.side_effect = RuntimeError("KB unavailable")

        with pytest.raises(RuntimeError, match="KB unavailable"):
            svc.retrieve_for_case("query", "case-1")

    def test_case_vector_search_error_propagates(self):
        """If case vector search raises, the error propagates."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.side_effect = RuntimeError("LanceDB error")

        with pytest.raises(RuntimeError, match="LanceDB error"):
            svc.retrieve_for_case("query", "case-1")

    def test_embedding_error_propagates(self):
        """If embedding fails, no search occurs."""
        svc = _make_svc()
        svc.embedding_service.embed_query.side_effect = RuntimeError("OOM")

        with pytest.raises(RuntimeError, match="OOM"):
            svc.retrieve_for_case("query", "case-1")

        # Neither search should have been called
        svc.case_vector_store.search_hybrid.assert_not_called()
        svc.retrieval_service.retrieve.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_stream_error_yields_sse_error_event(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """Runtime error during streaming → SSE error event."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat = MagicMock()
        mock_chat.generate_stream.side_effect = RuntimeError("Model timeout")
        mock_chat_fn.return_value = mock_chat

        from employee_help.api.casefile_routes import case_chat
        from employee_help.api.casefile_schemas import CaseChatRequest

        body = CaseChatRequest(query="Question")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)

        events = []
        evt_type = None
        async for chunk in response.body_iterator:
            for line in chunk.split("\n"):
                if line.startswith("event: "):
                    evt_type = line[7:]
                elif line.startswith("data: ") and evt_type:
                    events.append({"event": evt_type, "data": json.loads(line[6:])})
                    evt_type = None

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "Model timeout" in error_events[0]["data"]["message"]

    def test_empty_case_returns_fallback_message(self):
        """No results from either source → fallback message."""
        svc = _make_svc()

        stream, case_r, kb_r, meta = svc.generate_stream("query", "case-1")
        text = "".join(stream)

        assert "couldn't find relevant information" in text
        assert case_r == []
        assert kb_r == []
        assert meta == []


# ── Multi-turn integration ──────────────────────────────────────


class TestMultiTurnIntegration:
    """Multi-turn chat with dual-context retrieval."""

    def test_fresh_retrieval_each_turn(self):
        """Each turn calls retrieve_for_case independently."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [
            _raw_case(chunk_id="c-new")
        ]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            FakeStreamChunk(text="Turn 2 answer.", is_final=True, citations=[]),
        ])

        history = [
            {"role": "user", "content": "What about retaliation?"},
            {"role": "assistant", "content": "Retaliation claims under FEHA..."},
        ]

        stream, case_r, kb_r, _ = svc.generate_stream_multiturn(
            query="What statute applies?",
            case_id="case-1",
            conversation_history=history,
            turn_number=2,
        )
        list(stream)  # consume

        # Embed was called for this turn's query
        svc.embedding_service.embed_query.assert_called_once()
        # Case vector search was called
        svc.case_vector_store.search_hybrid.assert_called_once()
        # KB retrieval was called
        svc.retrieval_service.retrieve.assert_called_once()

    def test_short_followup_expansion_searches_both_sources(self):
        """Short follow-up expands query and searches both case + KB."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            FakeStreamChunk(text="Answer", is_final=True, citations=[]),
        ])

        history = [
            {"role": "user", "content": "Tell me about the termination date"},
            {"role": "assistant", "content": "March 15, 2025"},
        ]

        stream, _, _, _ = svc.generate_stream_multiturn(
            query="why?",
            case_id="case-1",
            conversation_history=history,
            turn_number=2,
        )
        list(stream)

        # The expanded query should be searched in case vector store
        case_args = svc.case_vector_store.search_hybrid.call_args.kwargs
        assert "termination" in case_args["query_text"].lower()
        assert "why?" in case_args["query_text"]

        # KB should also be searched with the expanded query
        kb_args = svc.retrieval_service.retrieve.call_args.kwargs
        assert "termination" in kb_args["query"].lower()

    def test_multiturn_doc_blocks_in_last_message(self):
        """Document blocks are placed in the last user message (current turn)."""
        svc = _make_svc()
        svc.case_vector_store.search_hybrid.return_value = [_raw_case()]
        svc.prompt_builder._load_template.side_effect = FileNotFoundError
        svc.prompt_builder._trim_history.return_value = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]

        svc.llm_client.generate_stream_multiturn.return_value = iter([
            FakeStreamChunk(text="Answer", is_final=True, citations=[]),
        ])

        stream, _, _, _ = svc.generate_stream_multiturn(
            query="Follow-up",
            case_id="case-1",
            conversation_history=[
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
            ],
            turn_number=2,
        )
        list(stream)

        call_kwargs = svc.llm_client.generate_stream_multiturn.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 3  # history(2) + current turn(1)

        # Last message is current turn with doc blocks + query text
        last_msg = messages[2]
        assert last_msg["role"] == "user"
        assert isinstance(last_msg["content"], list)
        # Should contain document blocks and a text block
        text_blocks = [
            b for b in last_msg["content"] if b.get("type") == "text"
        ]
        assert any("Follow-up" in b["text"] for b in text_blocks)

    def test_multiturn_empty_results_yields_fallback(self):
        """Both sources empty on follow-up → fallback message."""
        svc = _make_svc()

        stream, case_r, kb_r, meta = svc.generate_stream_multiturn(
            query="more?",
            case_id="case-1",
            turn_number=2,
        )
        text = "".join(stream)

        assert "couldn't find" in text
        assert case_r == []
        assert kb_r == []

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_multiturn_api_persists_both_turns(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """Multi-turn API call persists user + assistant turns correctly."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat = MagicMock()

        def fake_multiturn(query, case_id, **kwargs):
            metadata: list[dict] = []

            def gen():
                yield "Multi-turn response."
                metadata.append({
                    "citations": [],
                    "input_tokens": 250,
                    "output_tokens": 80,
                    "model": "claude-sonnet-4-6",
                })

            case_results = [
                MagicMock(
                    original_filename="evidence.pdf",
                    relevance_score=0.85,
                    file_id="f-1",
                    chunk_id="c-1",
                    heading_path="Page 1",
                ),
            ]
            return gen(), case_results, [], metadata

        mock_chat.generate_stream_multiturn.side_effect = fake_multiturn
        mock_chat_fn.return_value = mock_chat

        # Create an existing session
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )

        from employee_help.api.casefile_routes import case_chat
        from employee_help.api.casefile_schemas import (
            CaseChatRequest,
            CaseChatTurnItem,
        )

        body = CaseChatRequest(
            query="Follow up on this",
            session_id=session.id,
            conversation_history=[
                CaseChatTurnItem(role="user", content="First question"),
                CaseChatTurnItem(role="assistant", content="First answer"),
            ],
        )
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)

        # Consume stream
        async for _ in response.body_iterator:
            pass

        # Verify turns persisted
        turns = case_storage.list_chat_turns(session.id)
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[0].content == "Follow up on this"
        assert turns[1].role == "assistant"
        assert turns[1].content == "Multi-turn response."

        # Verify turn_number = 2
        assert turns[0].turn_number == 2
        assert turns[1].turn_number == 2


# ── Schema validation integration ───────────────────────────────


class TestChatSourceInfoSchema:
    """CaseChatSourceInfo schema handles all field combinations."""

    def test_case_file_source_all_fields(self):
        from employee_help.api.casefile_schemas import CaseChatSourceInfo

        info = CaseChatSourceInfo(
            source_type="case_file",
            title="complaint.pdf",
            relevance_score=0.92,
            file_id="f-1",
            chunk_id="c-1",
            heading_path="Page 3",
        )
        d = info.model_dump()
        assert d["source_type"] == "case_file"
        assert d["file_id"] == "f-1"
        assert d["chunk_id"] == "c-1"
        assert d["content_category"] is None

    def test_kb_source_all_fields(self):
        from employee_help.api.casefile_schemas import CaseChatSourceInfo

        info = CaseChatSourceInfo(
            source_type="knowledge_base",
            title="Cal. Lab. Code § 1102.5",
            relevance_score=0.88,
            chunk_id="kb-42",
            content_category="statutory_code",
            heading_path="Labor Code > § 1102.5",
        )
        d = info.model_dump()
        assert d["source_type"] == "knowledge_base"
        assert d["file_id"] is None
        assert d["content_category"] == "statutory_code"

    def test_minimal_source(self):
        from employee_help.api.casefile_schemas import CaseChatSourceInfo

        info = CaseChatSourceInfo(
            source_type="case_file",
            title="file.txt",
            relevance_score=0.5,
        )
        d = info.model_dump()
        assert d["file_id"] is None
        assert d["chunk_id"] is None
        assert d["heading_path"] is None
        assert d["content_category"] is None
