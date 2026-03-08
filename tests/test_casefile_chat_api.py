"""Tests for LITIGAGENT case chat API endpoints (L3.6).

Tests cover:
- Chat session CRUD in CaseStorage
- Chat turn persistence
- Pydantic schema validation (CaseChatRequest, etc.)
- POST /api/cases/{case_id}/chat SSE streaming
- GET /api/cases/{case_id}/chat/sessions
- GET /api/cases/{case_id}/chat/{session_id}
- Conversation history validation
- Turn limit enforcement
- Session creation and reuse
- Rate limiting integration
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from employee_help.api.casefile_schemas import (
    CaseChatRequest,
    CaseChatTurnItem,
    ChatHistoryResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatTurnResponse,
)
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseChatSession,
    CaseChatTurn,
)
from employee_help.storage.storage import Storage


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """Create an in-memory SQLite database with schema."""
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
    """CaseStorage backed by in-memory DB."""
    return CaseStorage(conn=db)


@pytest.fixture()
def sample_case(case_storage):
    """Create and return a sample case."""
    case = Case(
        name="Test Case",
        user_id="test-user",
        organization_id="test-org",
    )
    return case_storage.create_case(case)


# ── Schema validation tests ──────────────────────────────────────


class TestChatSchemas:
    def test_chat_request_valid(self):
        req = CaseChatRequest(query="What claims does the plaintiff have?")
        assert req.query == "What claims does the plaintiff have?"
        assert req.session_id is None
        assert req.conversation_history == []

    def test_chat_request_with_session(self):
        req = CaseChatRequest(
            query="Follow up",
            session_id="sess-123",
            conversation_history=[
                CaseChatTurnItem(role="user", content="Initial question"),
                CaseChatTurnItem(role="assistant", content="Initial answer"),
            ],
        )
        assert req.session_id == "sess-123"
        assert len(req.conversation_history) == 2

    def test_chat_request_empty_query_rejected(self):
        with pytest.raises(Exception):
            CaseChatRequest(query="")

    def test_chat_request_long_query_rejected(self):
        with pytest.raises(Exception):
            CaseChatRequest(query="A" * 2001)

    def test_chat_turn_item_valid_roles(self):
        user = CaseChatTurnItem(role="user", content="Hello")
        assert user.role == "user"
        asst = CaseChatTurnItem(role="assistant", content="Hi")
        assert asst.role == "assistant"

    def test_chat_turn_item_invalid_role(self):
        with pytest.raises(Exception):
            CaseChatTurnItem(role="system", content="x")

    def test_chat_request_sanitizes_query(self):
        req = CaseChatRequest(query="  test\x00query  ")
        # sanitize_text strips null bytes and trims whitespace
        assert "\x00" not in req.query
        assert not req.query.startswith(" ")


# ── CaseStorage chat session/turn CRUD ───────────────────────────


class TestChatSessionStorage:
    def test_create_chat_session(self, case_storage, sample_case):
        session = CaseChatSession(case_id=sample_case.id)
        created = case_storage.create_chat_session(session)
        assert created.id
        assert created.case_id == sample_case.id

    def test_get_chat_session(self, case_storage, sample_case):
        session = CaseChatSession(case_id=sample_case.id)
        created = case_storage.create_chat_session(session)
        fetched = case_storage.get_chat_session(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.case_id == sample_case.id

    def test_get_chat_session_not_found(self, case_storage):
        result = case_storage.get_chat_session("nonexistent")
        assert result is None

    def test_list_chat_sessions(self, case_storage, sample_case):
        s1 = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        s2 = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        sessions = case_storage.list_chat_sessions(sample_case.id)
        assert len(sessions) == 2
        # Ordered by updated_at DESC — most recent first
        ids = [s.id for s in sessions]
        assert s2.id in ids
        assert s1.id in ids

    def test_list_chat_sessions_empty(self, case_storage, sample_case):
        sessions = case_storage.list_chat_sessions(sample_case.id)
        assert sessions == []

    def test_update_chat_session_timestamp(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        original = session.updated_at
        case_storage.update_chat_session_timestamp(session.id)
        updated = case_storage.get_chat_session(session.id)
        assert updated.updated_at >= original

    def test_delete_chat_session(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        assert case_storage.delete_chat_session(session.id)
        assert case_storage.get_chat_session(session.id) is None

    def test_delete_chat_session_not_found(self, case_storage):
        assert not case_storage.delete_chat_session("nonexistent")

    def test_cascade_delete_with_case(self, case_storage, sample_case):
        """Deleting a case should cascade-delete its chat sessions."""
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        turn = CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="Hello",
        )
        case_storage.create_chat_turn(turn)
        case_storage.delete_case(sample_case.id)
        assert case_storage.get_chat_session(session.id) is None
        assert case_storage.list_chat_turns(session.id) == []


class TestChatTurnStorage:
    def test_create_chat_turn(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        turn = CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="What are the claims?",
        )
        created = case_storage.create_chat_turn(turn)
        assert created.id
        assert created.session_id == session.id
        assert created.turn_number == 1
        assert created.role == "user"

    def test_create_chat_turn_with_sources(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        sources = json.dumps({"case_sources": [{"file_id": "f1"}]})
        turn = CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="assistant",
            content="Based on the case files...",
            sources=sources,
        )
        created = case_storage.create_chat_turn(turn)
        assert created.sources == sources

    def test_list_chat_turns(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        for i, (role, content) in enumerate([
            ("user", "Question 1"),
            ("assistant", "Answer 1"),
            ("user", "Question 2"),
            ("assistant", "Answer 2"),
        ], start=1):
            case_storage.create_chat_turn(CaseChatTurn(
                session_id=session.id,
                turn_number=(i + 1) // 2,
                role=role,
                content=content,
            ))
        turns = case_storage.list_chat_turns(session.id)
        assert len(turns) == 4
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    def test_list_chat_turns_empty(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        turns = case_storage.list_chat_turns(session.id)
        assert turns == []

    def test_get_chat_session_turn_count(self, case_storage, sample_case):
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        assert case_storage.get_chat_session_turn_count(session.id) == 0
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="Hello",
        ))
        assert case_storage.get_chat_session_turn_count(session.id) == 1
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="assistant",
            content="Hi",
        ))
        assert case_storage.get_chat_session_turn_count(session.id) == 2

    def test_cascade_delete_turns_with_session(
        self, case_storage, sample_case
    ):
        """Deleting a session should cascade-delete its turns."""
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="Hello",
        ))
        case_storage.delete_chat_session(session.id)
        assert case_storage.list_chat_turns(session.id) == []


# ── History validation ───────────────────────────────────────────


class TestHistoryValidation:
    def test_valid_first_turn_no_history(self):
        from employee_help.api.casefile_routes import _validate_chat_history

        result = _validate_chat_history([], 1)
        assert result is None

    def test_valid_second_turn(self):
        from employee_help.api.casefile_routes import _validate_chat_history

        history = [
            MagicMock(role="user"),
            MagicMock(role="assistant"),
        ]
        result = _validate_chat_history(history, 2)
        assert result is None

    def test_wrong_history_length(self):
        from employee_help.api.casefile_routes import _validate_chat_history

        history = [MagicMock(role="user")]
        result = _validate_chat_history(history, 2)
        assert result is not None
        assert "length" in result.lower()

    def test_wrong_role_order(self):
        from employee_help.api.casefile_routes import _validate_chat_history

        history = [
            MagicMock(role="assistant"),
            MagicMock(role="user"),
        ]
        result = _validate_chat_history(history, 2)
        assert result is not None
        assert "role" in result.lower()


# ── API endpoint tests ───────────────────────────────────────────


@dataclass
class FakeUser:
    sub: str = "test-user"
    org: str = "test-org"
    email: str = "test@example.com"
    role: str = "admin"


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


def _make_mock_chat_service():
    """Create a mock CaseChatService for API tests.

    CaseChatService.generate_stream() returns:
      (text_stream: Iterator[str], case_results, kb_results, stream_metadata)
    The text_stream yields plain strings (not chunk objects).
    stream_metadata is a mutable list populated during iteration.
    """
    mock = MagicMock()

    def fake_stream(query, case_id, **kwargs):
        # stream_metadata is populated inside the generator
        metadata: list[dict] = []

        def text_gen():
            yield "Analysis: "
            yield "The case files show..."
            # Simulate what CaseChatService does: append metadata at end
            metadata.append({
                "citations": [],
                "input_tokens": 200,
                "output_tokens": 100,
                "model": "claude-sonnet-4-6",
            })

        case_results = [
            MagicMock(
                original_filename="complaint.pdf",
                relevance_score=0.9,
                file_id="f1",
                chunk_id="c1",
                heading_path="Page 1",
            ),
        ]
        kb_results = [
            MagicMock(
                heading_path="Cal. Lab. Code § 1102.5",
                relevance_score=0.8,
                chunk_id="kb1",
                content_category="statutory_code",
                citation="Cal. Lab. Code § 1102.5",
            ),
        ]
        return text_gen(), case_results, kb_results, metadata

    mock.generate_stream.side_effect = fake_stream
    mock.generate_stream_multiturn.side_effect = fake_stream
    return mock


async def _consume_sse(response) -> tuple[str, list[dict]]:
    """Consume an SSE StreamingResponse, return (full_text, parsed_events)."""
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    full = "".join(chunks)

    events = []
    current_event = None
    for line in full.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: ") and current_event:
            events.append({
                "event": current_event,
                "data": json.loads(line[6:]),
            })
            current_event = None
    return full, events


class TestCaseChatEndpoint:
    """Tests for POST /api/cases/{case_id}/chat."""

    @pytest.fixture()
    def db(self):
        import sqlite3 as _sqlite3
        from employee_help.storage.storage import _SCHEMA
        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = _sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA)
        yield conn
        conn.close()

    @pytest.fixture()
    def case_storage(self, db):
        return CaseStorage(conn=db)

    @pytest.fixture()
    def sample_case(self, case_storage):
        case = Case(
            name="Test Case",
            user_id="test-user",
            organization_id="test-org",
        )
        return case_storage.create_case(case)

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_single_turn(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        from employee_help.api.casefile_routes import case_chat

        body = CaseChatRequest(query="What claims exist?")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)

        assert response.media_type == "text/event-stream"

        _, events = await _consume_sse(response)

        event_types = [e["event"] for e in events]
        assert "sources" in event_types
        assert "token" in event_types
        assert "done" in event_types

        # Check sources event
        sources_data = next(e["data"] for e in events if e["event"] == "sources")
        assert "case_sources" in sources_data
        assert "kb_sources" in sources_data
        assert len(sources_data["case_sources"]) > 0
        assert sources_data["case_sources"][0]["source_type"] == "case_file"

        # Check done event
        done_data = next(e["data"] for e in events if e["event"] == "done")
        assert "session_id" in done_data
        assert done_data["turn_number"] == 1
        assert done_data["max_turns"] == 10

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_creates_session(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """First chat creates a new session."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        from employee_help.api.casefile_routes import case_chat

        body = CaseChatRequest(query="Hello")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)
        _, events = await _consume_sse(response)

        done = next(e["data"] for e in events if e["event"] == "done")
        session_id = done["session_id"]

        # Session should exist in DB
        session = case_storage.get_chat_session(session_id)
        assert session is not None
        assert session.case_id == sample_case.id

        # Turns should be persisted
        turns = case_storage.list_chat_turns(session_id)
        assert len(turns) == 2  # user + assistant
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_reuses_session(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        """Providing session_id reuses existing session."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )

        from employee_help.api.casefile_routes import case_chat

        body = CaseChatRequest(
            query="Follow up",
            session_id=session.id,
            conversation_history=[
                CaseChatTurnItem(role="user", content="First question"),
                CaseChatTurnItem(role="assistant", content="First answer"),
            ],
        )
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)
        _, events = await _consume_sse(response)

        done = next(e["data"] for e in events if e["event"] == "done")
        assert done["session_id"] == session.id
        assert done["turn_number"] == 2

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_invalid_session(
        self, mock_user, mock_storage_fn, mock_chat_fn,
        case_storage, sample_case,
    ):
        """Non-existent session_id should 404."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        from employee_help.api.casefile_routes import case_chat
        from fastapi import HTTPException

        body = CaseChatRequest(query="Hello", session_id="nonexistent")
        request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await case_chat(sample_case.id, body, request)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_turn_limit(
        self, mock_user, mock_storage_fn, mock_chat_fn,
        case_storage, sample_case,
    ):
        """Should return error SSE when turn limit exceeded."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        from employee_help.api.casefile_routes import case_chat

        # 10 turns = 20 history items
        history = []
        for i in range(10):
            history.append(CaseChatTurnItem(role="user", content=f"Q{i}"))
            history.append(CaseChatTurnItem(role="assistant", content=f"A{i}"))

        body = CaseChatRequest(
            query="One more?",
            conversation_history=history,
        )
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)
        _, events = await _consume_sse(response)

        assert any(
            e["event"] == "error" and "TURN_LIMIT" in e["data"]["message"]
            for e in events
        )

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_invalid_history(
        self, mock_user, mock_storage_fn, mock_chat_fn,
        case_storage, sample_case,
    ):
        """Bad history should 422."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        mock_chat_fn.return_value = _make_mock_chat_service()

        from employee_help.api.casefile_routes import case_chat
        from fastapi import HTTPException

        # Turn 2 expects 2 history items, but we provide 1
        body = CaseChatRequest(
            query="Follow up",
            conversation_history=[
                CaseChatTurnItem(role="user", content="Q1"),
            ],
        )
        request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await case_chat(sample_case.id, body, request)
        assert exc_info.value.status_code == 422


class TestChatSessionListEndpoint:
    """Tests for GET /api/cases/{case_id}/chat/sessions."""

    @pytest.fixture()
    def db(self):
        import sqlite3 as _sqlite3
        from employee_help.storage.storage import _SCHEMA
        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = _sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA)
        yield conn
        conn.close()

    @pytest.fixture()
    def case_storage(self, db):
        return CaseStorage(conn=db)

    @pytest.fixture()
    def sample_case(self, case_storage):
        case = Case(
            name="Test Case",
            user_id="test-user",
            organization_id="test-org",
        )
        return case_storage.create_case(case)

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_list_sessions_empty(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        from employee_help.api.casefile_routes import list_chat_sessions

        request = MagicMock()
        result = await list_chat_sessions(sample_case.id, request)
        assert result.sessions == []

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_list_sessions_with_data(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        s1 = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=s1.id,
            turn_number=1,
            role="user",
            content="Q1",
        ))
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=s1.id,
            turn_number=1,
            role="assistant",
            content="A1",
        ))

        from employee_help.api.casefile_routes import list_chat_sessions

        request = MagicMock()
        result = await list_chat_sessions(sample_case.id, request)
        assert len(result.sessions) == 1
        assert result.sessions[0].id == s1.id
        assert result.sessions[0].turn_count == 2


class TestChatHistoryEndpoint:
    """Tests for GET /api/cases/{case_id}/chat/{session_id}."""

    @pytest.fixture()
    def db(self):
        import sqlite3 as _sqlite3
        from employee_help.storage.storage import _SCHEMA
        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = _sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA)
        yield conn
        conn.close()

    @pytest.fixture()
    def case_storage(self, db):
        return CaseStorage(conn=db)

    @pytest.fixture()
    def sample_case(self, case_storage):
        case = Case(
            name="Test Case",
            user_id="test-user",
            organization_id="test-org",
        )
        return case_storage.create_case(case)

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_get_history(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        session = case_storage.create_chat_session(
            CaseChatSession(case_id=sample_case.id)
        )
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="user",
            content="What claims?",
        ))
        sources_json = json.dumps({"case_sources": [{"file_id": "f1"}]})
        case_storage.create_chat_turn(CaseChatTurn(
            session_id=session.id,
            turn_number=1,
            role="assistant",
            content="Based on the files...",
            sources=sources_json,
        ))

        from employee_help.api.casefile_routes import get_chat_history

        request = MagicMock()
        result = await get_chat_history(sample_case.id, session.id, request)
        assert result.session_id == session.id
        assert result.case_id == sample_case.id
        assert len(result.turns) == 2
        assert result.turns[0].role == "user"
        assert result.turns[1].role == "assistant"
        assert result.turns[1].sources is not None

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_get_history_not_found(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        from employee_help.api.casefile_routes import get_chat_history
        from fastapi import HTTPException

        request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_chat_history(sample_case.id, "nonexistent", request)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_get_history_wrong_case(
        self, mock_user, mock_storage_fn,
        case_storage, sample_case,
    ):
        """Session from a different case should 404."""
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage

        other_case = case_storage.create_case(Case(
            name="Other", user_id="test-user", organization_id="test-org",
        ))
        session = case_storage.create_chat_session(
            CaseChatSession(case_id=other_case.id)
        )

        from employee_help.api.casefile_routes import get_chat_history
        from fastapi import HTTPException

        request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_chat_history(sample_case.id, session.id, request)
        assert exc_info.value.status_code == 404


class TestChatServiceUnavailable:
    """Tests for when CaseChatService is not available."""

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_chat_503_when_service_unavailable(
        self, mock_user, mock_storage_fn,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = MagicMock()

        from employee_help.api.casefile_routes import case_chat
        from fastapi import HTTPException

        body = CaseChatRequest(query="Hello")
        request = MagicMock()

        with patch(
            "employee_help.api.casefile_routes._get_case_chat_service",
            side_effect=HTTPException(503, "Case chat service not available"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await case_chat("case-1", body, request)
            assert exc_info.value.status_code == 503


class TestChatStreamError:
    """Test error handling during streaming."""

    @pytest.fixture()
    def db(self):
        import sqlite3 as _sqlite3
        from employee_help.storage.storage import _SCHEMA
        conn = _sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = _sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA)
        yield conn
        conn.close()

    @pytest.fixture()
    def case_storage(self, db):
        return CaseStorage(conn=db)

    @pytest.fixture()
    def sample_case(self, case_storage):
        case = Case(
            name="Test Case",
            user_id="test-user",
            organization_id="test-org",
        )
        return case_storage.create_case(case)

    @pytest.mark.asyncio(loop_scope="function")
    @patch("employee_help.api.casefile_routes._audit")
    @patch("employee_help.api.casefile_routes._get_case_chat_service")
    @patch("employee_help.api.casefile_routes._get_case_storage")
    @patch("employee_help.api.casefile_routes._require_user")
    async def test_stream_error_emits_sse_error(
        self, mock_user, mock_storage_fn, mock_chat_fn, mock_audit,
        case_storage, sample_case,
    ):
        mock_user.return_value = FakeUser()
        mock_storage_fn.return_value = case_storage
        error_service = MagicMock()
        error_service.generate_stream.side_effect = RuntimeError("LLM down")
        mock_chat_fn.return_value = error_service

        from employee_help.api.casefile_routes import case_chat

        body = CaseChatRequest(query="Hello")
        request = MagicMock()
        response = await case_chat(sample_case.id, body, request)
        _, events = await _consume_sse(response)

        assert any(
            e["event"] == "error" and "LLM down" in e["data"]["message"]
            for e in events
        )
