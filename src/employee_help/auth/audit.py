"""Append-only audit logger writing to the audit_log table."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class AuditLogger:
    """Append-only audit logger for security-sensitive operations.

    Writes to the audit_log table. No update or delete operations
    are exposed — the log is immutable once written.
    """

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if conn is not None:
            self._conn = conn
            self._owns_conn = False
        elif db_path is not None:
            p = Path(db_path)
            if str(p) != ":memory:":
                p.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(p), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._owns_conn = True
        else:
            raise ValueError("Either conn or db_path must be provided")

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()

    # ── Write ─────────────────────────────────────────────────────

    def log(
        self,
        action: str,
        *,
        user_id: str | None = None,
        organization_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Insert a single audit log entry. Returns the row id."""
        now = datetime.now(tz=UTC).isoformat()
        meta_json = json.dumps(metadata) if metadata else None
        cur = self._conn.execute(
            """INSERT INTO audit_log
               (user_id, organization_id, action, resource_type, resource_id,
                ip_address, user_agent, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                organization_id,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                meta_json,
                now,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def log_from_request(
        self,
        action: str,
        request,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Log an action, extracting user/IP/user-agent from a FastAPI Request.

        If ``request.state.user`` is an ``AccessTokenClaims``, its ``sub``
        and ``org`` fields are used.  Otherwise user_id and organization_id
        are ``None`` (anonymous action).
        """
        user = getattr(getattr(request, "state", None), "user", None)
        user_id: str | None = None
        org_id: str | None = None
        if user is not None:
            user_id = getattr(user, "sub", None)
            org_id = getattr(user, "org", None)

        # IP address — honour X-Forwarded-For
        ip_address: str | None = None
        forwarded = request.headers.get("x-forwarded-for") if hasattr(request, "headers") else None
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        elif hasattr(request, "client") and request.client:
            ip_address = request.client.host

        user_agent = request.headers.get("user-agent") if hasattr(request, "headers") else None

        return self.log(
            action,
            user_id=user_id,
            organization_id=org_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )

    # ── Read (user's own log only) ────────────────────────────────

    def get_user_log(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
    ) -> list[dict]:
        """Fetch audit log entries for a specific user."""
        sql = "SELECT * FROM audit_log WHERE user_id = ?"
        params: list = [user_id]
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_user_entries(
        self,
        user_id: str,
        *,
        action: str | None = None,
    ) -> int:
        """Count audit log entries for a user (for pagination)."""
        sql = "SELECT COUNT(*) FROM audit_log WHERE user_id = ?"
        params: list = [user_id]
        if action:
            sql += " AND action = ?"
            params.append(action)
        return self._conn.execute(sql, params).fetchone()[0]

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        # Parse metadata JSON back to dict
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
