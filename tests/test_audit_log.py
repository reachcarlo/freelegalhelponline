"""Tests for audit logging (A3.1)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from employee_help.auth.audit import AuditLogger
from employee_help.storage.storage import Storage


# ── Fixtures ───────────────────────────────────────────────────


def _create_test_user(
    conn: sqlite3.Connection, user_id: str, org_id: str | None = None,
) -> None:
    """Insert a minimal user row (and org) to satisfy FK constraints."""
    from datetime import UTC, datetime

    now = datetime.now(tz=UTC).isoformat()
    if org_id:
        conn.execute(
            """INSERT OR IGNORE INTO organizations
               (id, name, slug, plan_tier, sso_provider, sso_config,
                max_seats, created_at, updated_at)
               VALUES (?, ?, ?, 'free', NULL, NULL, 1, ?, ?)""",
            (org_id, f"Org {org_id}", f"org-{org_id}", now, now),
        )
    conn.execute(
        """INSERT OR IGNORE INTO users
           (id, provider, provider_user_id, email, display_name,
            avatar_url, is_active, created_at, last_login_at)
           VALUES (?, 'test', ?, ?, ?, NULL, 1, ?, ?)""",
        (user_id, user_id, f"{user_id}@test.com", user_id, now, now),
    )
    conn.commit()


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def audit(storage: Storage) -> AuditLogger:
    """AuditLogger sharing the same DB connection as Storage."""
    # Pre-create test users for FK constraints
    _create_test_user(storage._conn, "u1")
    _create_test_user(storage._conn, "u2")
    _create_test_user(storage._conn, "u3")
    a = AuditLogger(conn=storage._conn)
    return a


def _mock_request(
    user_id: str | None = None,
    org_id: str | None = None,
    ip: str = "10.0.0.1",
    user_agent: str = "TestBrowser/1.0",
    forwarded_for: str | None = None,
) -> MagicMock:
    """Create a mock FastAPI Request with optional user claims."""
    req = MagicMock()
    headers = {"user-agent": user_agent}
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for
    req.headers = headers
    req.client = SimpleNamespace(host=ip)

    if user_id:
        req.state.user = SimpleNamespace(sub=user_id, org=org_id or "org-1")
    else:
        req.state.user = None

    return req


# ── Unit: AuditLogger.log() ──────────────────────────────────


class TestAuditLogBasic:
    def test_log_creates_entry(self, audit: AuditLogger, storage: Storage):
        row_id = audit.log("case.create", user_id="u1")
        assert row_id > 0
        row = storage._conn.execute(
            "SELECT * FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row is not None
        assert row["action"] == "case.create"
        assert row["user_id"] == "u1"

    def test_log_stores_metadata_as_json(self, audit: AuditLogger, storage: Storage):
        meta = {"case_id": "abc", "filename": "doc.pdf"}
        row_id = audit.log("file.upload", metadata=meta)
        row = storage._conn.execute(
            "SELECT metadata FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert json.loads(row["metadata"]) == meta

    def test_log_sets_created_at(self, audit: AuditLogger, storage: Storage):
        before = datetime.now(tz=UTC).isoformat()
        row_id = audit.log("auth.login")
        after = datetime.now(tz=UTC).isoformat()
        row = storage._conn.execute(
            "SELECT created_at FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert before <= row["created_at"] <= after

    def test_log_returns_row_id(self, audit: AuditLogger):
        id1 = audit.log("auth.login")
        id2 = audit.log("auth.logout")
        assert id2 > id1

    def test_log_null_optional_fields(self, audit: AuditLogger, storage: Storage):
        row_id = audit.log("auth.login")
        row = storage._conn.execute(
            "SELECT * FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["user_id"] is None
        assert row["organization_id"] is None
        assert row["resource_type"] is None
        assert row["resource_id"] is None
        assert row["ip_address"] is None
        assert row["user_agent"] is None
        assert row["metadata"] is None

    def test_log_all_fields(self, audit: AuditLogger, storage: Storage):
        _create_test_user(storage._conn, "u1", org_id="org1")
        row_id = audit.log(
            "file.upload",
            user_id="u1",
            organization_id="org1",
            resource_type="file",
            resource_id="f1",
            ip_address="1.2.3.4",
            user_agent="Bot/1.0",
            metadata={"size": 1024},
        )
        row = storage._conn.execute(
            "SELECT * FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["user_id"] == "u1"
        assert row["organization_id"] == "org1"
        assert row["resource_type"] == "file"
        assert row["resource_id"] == "f1"
        assert row["ip_address"] == "1.2.3.4"
        assert row["user_agent"] == "Bot/1.0"
        assert json.loads(row["metadata"]) == {"size": 1024}


# ── Unit: AuditLogger.log_from_request() ─────────────────────


class TestAuditLogFromRequest:
    def test_extracts_user_claims(self, audit: AuditLogger, storage: Storage):
        _create_test_user(storage._conn, "user-abc", org_id="org-xyz")
        req = _mock_request(user_id="user-abc", org_id="org-xyz")
        row_id = audit.log_from_request("case.create", req)
        row = storage._conn.execute(
            "SELECT * FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["user_id"] == "user-abc"
        assert row["organization_id"] == "org-xyz"

    def test_extracts_ip_from_client(self, audit: AuditLogger, storage: Storage):
        req = _mock_request(ip="192.168.1.5")
        row_id = audit.log_from_request("auth.login", req)
        row = storage._conn.execute(
            "SELECT ip_address FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["ip_address"] == "192.168.1.5"

    def test_extracts_ip_from_forwarded_for(self, audit: AuditLogger, storage: Storage):
        req = _mock_request(forwarded_for="1.2.3.4, 5.6.7.8")
        row_id = audit.log_from_request("auth.login", req)
        row = storage._conn.execute(
            "SELECT ip_address FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["ip_address"] == "1.2.3.4"

    def test_extracts_user_agent(self, audit: AuditLogger, storage: Storage):
        req = _mock_request(user_agent="MyApp/2.0")
        row_id = audit.log_from_request("auth.login", req)
        row = storage._conn.execute(
            "SELECT user_agent FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["user_agent"] == "MyApp/2.0"

    def test_no_user_sets_null(self, audit: AuditLogger, storage: Storage):
        req = _mock_request()  # No user_id
        row_id = audit.log_from_request("auth.login_failed", req)
        row = storage._conn.execute(
            "SELECT user_id, organization_id FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["user_id"] is None
        assert row["organization_id"] is None

    def test_passes_metadata(self, audit: AuditLogger, storage: Storage):
        _create_test_user(storage._conn, "u1", org_id="org-1")
        req = _mock_request(user_id="u1")
        row_id = audit.log_from_request(
            "file.upload", req,
            resource_type="file",
            resource_id="f123",
            metadata={"case_id": "c1"},
        )
        row = storage._conn.execute(
            "SELECT * FROM audit_log WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["resource_type"] == "file"
        assert row["resource_id"] == "f123"
        assert json.loads(row["metadata"]) == {"case_id": "c1"}


# ── Unit: AuditLogger.get_user_log() ─────────────────────────


class TestAuditLogQuery:
    def test_returns_user_entries(self, audit: AuditLogger):
        audit.log("case.create", user_id="u1")
        audit.log("case.archive", user_id="u1")
        audit.log("case.create", user_id="u2")  # different user

        entries = audit.get_user_log("u1")
        assert len(entries) == 2
        assert all(e["user_id"] == "u1" for e in entries)

    def test_pagination(self, audit: AuditLogger):
        for i in range(10):
            audit.log(f"action.{i}", user_id="u1")

        page1 = audit.get_user_log("u1", limit=3, offset=0)
        page2 = audit.get_user_log("u1", limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        # No overlap
        ids1 = {e["id"] for e in page1}
        ids2 = {e["id"] for e in page2}
        assert ids1.isdisjoint(ids2)

    def test_filter_by_action(self, audit: AuditLogger):
        audit.log("case.create", user_id="u1")
        audit.log("file.upload", user_id="u1")
        audit.log("case.archive", user_id="u1")

        entries = audit.get_user_log("u1", action="case.create")
        assert len(entries) == 1
        assert entries[0]["action"] == "case.create"

    def test_empty_result(self, audit: AuditLogger):
        entries = audit.get_user_log("nonexistent")
        assert entries == []

    def test_ordered_newest_first(self, audit: AuditLogger):
        audit.log("first", user_id="u1")
        audit.log("second", user_id="u1")
        entries = audit.get_user_log("u1")
        assert entries[0]["action"] == "second"
        assert entries[1]["action"] == "first"

    def test_count_user_entries(self, audit: AuditLogger):
        audit.log("case.create", user_id="u1")
        audit.log("file.upload", user_id="u1")
        audit.log("case.create", user_id="u2")

        assert audit.count_user_entries("u1") == 2
        assert audit.count_user_entries("u2") == 1
        assert audit.count_user_entries("u3") == 0

    def test_count_with_action_filter(self, audit: AuditLogger):
        audit.log("case.create", user_id="u1")
        audit.log("file.upload", user_id="u1")
        audit.log("case.create", user_id="u1")

        assert audit.count_user_entries("u1", action="case.create") == 2
        assert audit.count_user_entries("u1", action="file.upload") == 1

    def test_metadata_deserialized(self, audit: AuditLogger):
        audit.log("file.upload", user_id="u1", metadata={"size": 42})
        entries = audit.get_user_log("u1")
        assert entries[0]["metadata"] == {"size": 42}


# ── Append-only enforcement ──────────────────────────────────


class TestAppendOnly:
    def test_no_update_method(self):
        """AuditLogger must not expose update or delete methods."""
        methods = dir(AuditLogger)
        assert "update" not in methods
        assert "delete" not in methods
        assert "delete_entry" not in methods
        assert "update_entry" not in methods

    def test_constructor_requires_conn_or_path(self):
        with pytest.raises(ValueError, match="Either conn or db_path"):
            AuditLogger()


# ── Integration: Route audit logging ─────────────────────────


class TestRouteAuditIntegration:
    """Integration tests verifying audit entries are created by route handlers.

    Uses TestClient with mocked services, similar to test_casefile_routes.py.
    """

    @pytest.fixture
    def setup(self, tmp_path):
        """Set up a test app with real audit logging."""
        from contextlib import asynccontextmanager

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import employee_help.api.deps as deps
        from employee_help.api.casefile_routes import casefile_router
        from employee_help.api.main import auth_middleware, rate_limit_middleware
        from employee_help.auth.tokens import create_access_token

        # Create schema via Storage (creates its own connection)
        db_path = tmp_path / "test.db"
        s = Storage(db_path=db_path)
        s.close()

        # Reopen with check_same_thread=False for TestClient
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Create test user + org in DB for FK constraints
        _create_test_user(conn, "test-user", org_id="test-org")

        # Create case storage + audit logger on same shared connection
        from employee_help.storage.case_storage import CaseStorage

        cs = CaseStorage(conn=conn)
        audit = AuditLogger(conn=conn)

        # Create a test JWT
        secret = "test-secret-audit-xxxxxxxxxxxxxxxxx"
        token = create_access_token(
            user_id="test-user",
            org_id="test-org",
            role="owner",
            email="test@example.com",
            secret=secret,
        )

        # Set up session manager mock
        from employee_help.auth.session import SessionManager
        from employee_help.auth.tokens import AccessTokenClaims

        claims = AccessTokenClaims(
            sub="test-user", org="test-org", role="owner",
            email="test@example.com", iat=0, exp=999999999999,
        )
        mock_sm = MagicMock(spec=SessionManager)
        mock_sm.validate.return_value = claims

        # Save old deps
        old_cs = deps._case_storage
        old_audit = deps._audit_logger
        old_sm = deps._session_manager

        deps._case_storage = cs
        deps._audit_logger = audit
        deps._session_manager = mock_sm

        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        app = FastAPI(lifespan=noop_lifespan)
        app.middleware("http")(rate_limit_middleware)
        app.middleware("http")(auth_middleware)
        app.include_router(casefile_router)

        # Clear rate limit stores
        from employee_help.api.main import _rate_limit_store

        _rate_limit_store.clear()

        client = TestClient(app, raise_server_exceptions=False, cookies={"access_token": token})

        yield SimpleNamespace(
            client=client,
            audit=audit,
            case_storage=cs,
            token=token,
        )

        deps._case_storage = old_cs
        deps._audit_logger = old_audit
        deps._session_manager = old_sm
        _rate_limit_store.clear()
        conn.close()

    def test_case_create_audit(self, setup):
        resp = setup.client.post("/api/cases", json={"name": "Test Case"})
        assert resp.status_code == 201
        case_id = resp.json()["id"]

        entries = setup.audit.get_user_log("test-user", action="case.create")
        assert len(entries) == 1
        assert entries[0]["resource_type"] == "case"
        assert entries[0]["resource_id"] == case_id

    def test_case_archive_audit(self, setup):
        resp = setup.client.post("/api/cases", json={"name": "Archive Me"})
        case_id = resp.json()["id"]

        setup.client.delete(f"/api/cases/{case_id}")

        entries = setup.audit.get_user_log("test-user", action="case.archive")
        assert len(entries) == 1
        assert entries[0]["resource_id"] == case_id

    def test_note_crud_audit(self, setup):
        # Create case
        resp = setup.client.post("/api/cases", json={"name": "Note Case"})
        case_id = resp.json()["id"]

        # Create note
        resp = setup.client.post(f"/api/cases/{case_id}/notes", json={"content": "test note"})
        assert resp.status_code == 201
        note_id = resp.json()["id"]

        # Update note
        setup.client.patch(f"/api/cases/{case_id}/notes/{note_id}", json={"content": "updated"})

        # Delete note
        setup.client.delete(f"/api/cases/{case_id}/notes/{note_id}")

        creates = setup.audit.get_user_log("test-user", action="note.create")
        updates = setup.audit.get_user_log("test-user", action="note.update")
        deletes = setup.audit.get_user_log("test-user", action="note.delete")
        assert len(creates) == 1
        assert len(updates) == 1
        assert len(deletes) == 1

    def test_gate_full_lifecycle_audited(self, setup):
        """Gate test: every case/file/note operation creates an audit entry."""
        # Create case
        resp = setup.client.post("/api/cases", json={"name": "Gate Case"})
        case_id = resp.json()["id"]

        # Create note
        resp = setup.client.post(f"/api/cases/{case_id}/notes", json={"content": "a note"})
        note_id = resp.json()["id"]

        # Update note
        setup.client.patch(f"/api/cases/{case_id}/notes/{note_id}", json={"content": "updated"})

        # Delete note
        setup.client.delete(f"/api/cases/{case_id}/notes/{note_id}")

        # Archive case
        setup.client.delete(f"/api/cases/{case_id}")

        # Verify all actions logged
        all_entries = setup.audit.get_user_log("test-user", limit=100)
        actions = [e["action"] for e in all_entries]
        assert "case.create" in actions
        assert "note.create" in actions
        assert "note.update" in actions
        assert "note.delete" in actions
        assert "case.archive" in actions

        # Verify total count
        total = setup.audit.count_user_entries("test-user")
        assert total == 5


# ── Audit log endpoint tests ─────────────────────────────────


class TestAuditLogEndpoint:
    @pytest.fixture
    def setup(self, tmp_path):
        from contextlib import asynccontextmanager

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import employee_help.api.deps as deps
        from employee_help.api.auth_routes import auth_router
        from employee_help.auth.session import SessionManager
        from employee_help.auth.tokens import AccessTokenClaims, create_access_token

        db_path = tmp_path / "test.db"
        s = Storage(db_path=db_path)
        audit = AuditLogger(db_path=db_path)

        # Create test users in DB for FK constraints
        _create_test_user(s._conn, "ep-user")
        _create_test_user(s._conn, "other-user")

        secret = "test-audit-endpoint-secret-xxxxx"
        token = create_access_token(
            user_id="ep-user",
            org_id="ep-org",
            role="owner",
            email="ep@example.com",
            secret=secret,
        )
        claims = AccessTokenClaims(
            sub="ep-user", org="ep-org", role="owner",
            email="ep@example.com", iat=0, exp=999999999999,
        )
        mock_sm = MagicMock(spec=SessionManager)
        mock_sm.validate.return_value = claims

        old_audit = deps._audit_logger
        old_sm = deps._session_manager

        deps._audit_logger = audit
        deps._session_manager = mock_sm

        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        app = FastAPI(lifespan=noop_lifespan)
        app.include_router(auth_router)

        client = TestClient(app, raise_server_exceptions=False, cookies={"access_token": token})

        yield SimpleNamespace(
            client=client,
            audit=audit,
            storage=s,
        )

        deps._audit_logger = old_audit
        deps._session_manager = old_sm
        audit.close()
        s.close()

    def test_returns_user_entries(self, setup):
        setup.audit.log("case.create", user_id="ep-user")
        setup.audit.log("file.upload", user_id="ep-user")

        resp = setup.client.get("/api/auth/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2

    def test_requires_auth(self, setup):
        from fastapi.testclient import TestClient

        # Create a client without cookies
        client = TestClient(setup.client.app, raise_server_exceptions=False)
        resp = client.get("/api/auth/audit-log")
        assert resp.status_code == 401

    def test_pagination(self, setup):
        for i in range(10):
            setup.audit.log(f"action.{i}", user_id="ep-user")

        resp = setup.client.get("/api/auth/audit-log?limit=3&offset=0")
        data = resp.json()
        assert len(data["entries"]) == 3
        assert data["total"] == 10
        assert data["limit"] == 3
        assert data["offset"] == 0

    def test_filter_by_action(self, setup):
        setup.audit.log("case.create", user_id="ep-user")
        setup.audit.log("file.upload", user_id="ep-user")
        setup.audit.log("case.create", user_id="ep-user")

        resp = setup.client.get("/api/auth/audit-log?action=case.create")
        data = resp.json()
        assert data["total"] == 2
        assert all(e["action"] == "case.create" for e in data["entries"])

    def test_does_not_expose_other_users(self, setup):
        setup.audit.log("case.create", user_id="ep-user")
        setup.audit.log("case.create", user_id="other-user")

        resp = setup.client.get("/api/auth/audit-log")
        data = resp.json()
        assert data["total"] == 1
        assert all(e["user_id"] == "ep-user" for e in data["entries"])

    def test_limit_clamped(self, setup):
        resp = setup.client.get("/api/auth/audit-log?limit=500")
        data = resp.json()
        assert data["limit"] == 200  # max clamp
