"""Tests for PII redaction in application logs (A3.4)."""

from __future__ import annotations

import pytest

from employee_help.logging import _REDACTED, redact_pii


# ── Helper ──────────────────────────────────────────────────────


def _process(event_dict: dict) -> dict:
    """Run the redaction processor on an event dict."""
    return redact_pii(None, "info", event_dict.copy())


# ── Direct key redaction ────────────────────────────────────────


class TestKnownKeyRedaction:
    """Keys in _REDACT_KEYS must be fully replaced with [REDACTED]."""

    def test_email_key_redacted(self):
        result = _process({"event": "login", "email": "alice@example.com"})
        assert result["email"] == _REDACTED

    def test_filename_key_redacted(self):
        result = _process({"event": "upload", "filename": "complaint_draft.pdf"})
        assert result["filename"] == _REDACTED

    def test_file_name_key_redacted(self):
        result = _process({"event": "upload", "file_name": "deposition.docx"})
        assert result["file_name"] == _REDACTED

    def test_display_name_key_redacted(self):
        result = _process({"event": "login", "display_name": "Alice Smith"})
        assert result["display_name"] == _REDACTED

    def test_name_key_redacted(self):
        result = _process({"event": "case_created", "name": "Smith v. Jones"})
        assert result["name"] == _REDACTED

    def test_ip_address_key_redacted(self):
        result = _process({"event": "request", "ip_address": "192.168.1.1"})
        assert result["ip_address"] == _REDACTED

    def test_ip_key_redacted(self):
        result = _process({"event": "request", "ip": "10.0.0.1"})
        assert result["ip"] == _REDACTED

    def test_client_ip_key_redacted(self):
        result = _process({"event": "request", "client_ip": "172.16.0.1"})
        assert result["client_ip"] == _REDACTED

    def test_remote_addr_key_redacted(self):
        result = _process({"event": "request", "remote_addr": "8.8.8.8"})
        assert result["remote_addr"] == _REDACTED

    def test_user_agent_key_redacted(self):
        result = _process({"event": "request", "user_agent": "Mozilla/5.0"})
        assert result["user_agent"] == _REDACTED


# ── Safe keys are NOT redacted ──────────────────────────────────


class TestSafeKeys:
    """Keys in _SAFE_KEYS must pass through untouched."""

    def test_provider_name_preserved(self):
        result = _process({"event": "login", "provider_name": "google"})
        assert result["provider_name"] == "google"

    def test_source_name_preserved(self):
        result = _process({"event": "refresh", "source_name": "labor_code"})
        assert result["source_name"] == "labor_code"

    def test_model_name_preserved(self):
        result = _process({"event": "gen", "model_name": "claude-haiku-4-5"})
        assert result["model_name"] == "claude-haiku-4-5"

    def test_table_name_preserved(self):
        result = _process({"event": "migrate", "table_name": "cases"})
        assert result["table_name"] == "cases"


# ── Embedded email scrubbing ────────────────────────────────────


class TestEmbeddedEmailScrubbing:
    """Email addresses embedded in string values are replaced inline."""

    def test_email_in_message_redacted(self):
        result = _process({"event": "User alice@example.com logged in"})
        assert "alice@example.com" not in result["event"]
        assert _REDACTED in result["event"]

    def test_multiple_emails_redacted(self):
        result = _process({
            "event": "test",
            "msg": "from alice@a.com to bob@b.com",
        })
        assert "alice@a.com" not in result["msg"]
        assert "bob@b.com" not in result["msg"]

    def test_no_email_passes_through(self):
        result = _process({"event": "test", "msg": "no email here"})
        assert result["msg"] == "no email here"


# ── Non-string values are untouched ─────────────────────────────


class TestNonStringValues:
    """Numeric, bool, and None values pass through without error."""

    def test_int_value_preserved(self):
        result = _process({"event": "test", "count": 42})
        assert result["count"] == 42

    def test_none_value_preserved(self):
        result = _process({"event": "test", "extra": None})
        assert result["extra"] is None

    def test_bool_value_preserved(self):
        result = _process({"event": "test", "ok": True})
        assert result["ok"] is True


# ── Standard log fields are preserved ───────────────────────────


class TestStandardFieldsPreserved:
    """Fields that should never be redacted."""

    def test_event_preserved(self):
        result = _process({"event": "http_request"})
        assert result["event"] == "http_request"

    def test_user_id_preserved(self):
        result = _process({"event": "login", "user_id": "abc-123-def"})
        assert result["user_id"] == "abc-123-def"

    def test_case_id_preserved(self):
        result = _process({"event": "upload", "case_id": "case-uuid-456"})
        assert result["case_id"] == "case-uuid-456"

    def test_file_id_preserved(self):
        result = _process({"event": "upload", "file_id": "file-uuid-789"})
        assert result["file_id"] == "file-uuid-789"

    def test_status_code_preserved(self):
        result = _process({"event": "req", "status": 200})
        assert result["status"] == 200

    def test_duration_preserved(self):
        result = _process({"event": "req", "duration_ms": 42})
        assert result["duration_ms"] == 42

    def test_method_preserved(self):
        result = _process({"event": "req", "method": "POST"})
        assert result["method"] == "POST"

    def test_path_preserved(self):
        result = _process({"event": "req", "path": "/api/ask"})
        assert result["path"] == "/api/ask"


# ── Multiple PII fields in one event ───────────────────────────


class TestMultipleFields:
    """Multiple PII fields in a single log event are all redacted."""

    def test_email_and_filename_both_redacted(self):
        result = _process({
            "event": "upload",
            "email": "user@test.com",
            "filename": "private.pdf",
            "user_id": "uuid-safe",
        })
        assert result["email"] == _REDACTED
        assert result["filename"] == _REDACTED
        assert result["user_id"] == "uuid-safe"

    def test_all_pii_keys_redacted_together(self):
        result = _process({
            "event": "login",
            "email": "a@b.com",
            "display_name": "Alice",
            "ip_address": "1.2.3.4",
            "user_agent": "Chrome",
            "user_id": "safe-uuid",
        })
        assert result["email"] == _REDACTED
        assert result["display_name"] == _REDACTED
        assert result["ip_address"] == _REDACTED
        assert result["user_agent"] == _REDACTED
        assert result["user_id"] == "safe-uuid"


# ── Integration: structlog processor chain ──────────────────────


class TestStructlogIntegration:
    """Verify the processor works within a real structlog chain."""

    def test_processor_is_callable(self):
        """redact_pii has the correct structlog processor signature."""
        result = redact_pii(None, "info", {"event": "test", "email": "x@y.com"})
        assert result["email"] == _REDACTED

    def test_processor_returns_dict(self):
        result = redact_pii(None, "info", {"event": "test"})
        assert isinstance(result, dict)


# ── Verify removed PII from actual log calls ───────────────────


class TestLogCallPIIRemoval:
    """Verify that known log calls no longer include PII fields.

    These tests read the source files to confirm PII was removed at
    the call site (defense in depth — even without the processor).
    """

    def _read_source(self, rel_path: str) -> str:
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "src" / "employee_help" / rel_path
        return src.read_text()

    def test_auth_routes_login_no_email(self):
        source = self._read_source("api/auth_routes.py")
        # The user_logged_in log call must not contain email=
        import re
        match = re.search(r'logger\.info\(\s*"user_logged_in".*?\)', source, re.DOTALL)
        assert match is not None, "user_logged_in log call not found"
        assert "email=" not in match.group(0)

    def test_casefile_routes_upload_no_filename(self):
        source = self._read_source("api/casefile_routes.py")
        import re
        match = re.search(r'logger\.info\(\s*"file_uploaded".*?\)', source, re.DOTALL)
        assert match is not None, "file_uploaded log call not found"
        assert "filename=" not in match.group(0)

    def test_casefile_routes_create_no_name(self):
        source = self._read_source("api/casefile_routes.py")
        import re
        match = re.search(r'logger\.info\(\s*"case_created".*?\)', source, re.DOTALL)
        assert match is not None, "case_created log call not found"
        assert "name=" not in match.group(0)
