"""SQLite-backed store for query analytics and user feedback."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from employee_help.feedback.models import FeedbackEntry, QueryLogEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL UNIQUE,
    query_hash TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_estimate REAL NOT NULL DEFAULT 0.0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    session_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL REFERENCES query_log(query_id),
    rating INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    turn_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_log_created ON query_log(created_at);
CREATE INDEX IF NOT EXISTS idx_query_log_mode ON query_log(mode);
CREATE INDEX IF NOT EXISTS idx_query_log_session ON query_log(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_query_id ON feedback(query_id);
CREATE INDEX IF NOT EXISTS idx_session_created ON conversation_session(created_at);
"""

_MIGRATIONS = [
    # Add session_id column to query_log if missing (backward compatible)
    ("query_log_session_id", "ALTER TABLE query_log ADD COLUMN session_id TEXT"),
    # Create conversation_session table if missing
    (
        "conversation_session_table",
        """CREATE TABLE IF NOT EXISTS conversation_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            mode TEXT NOT NULL,
            turn_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL
        )""",
    ),
    (
        "idx_query_log_session",
        "CREATE INDEX IF NOT EXISTS idx_query_log_session ON query_log(session_id)",
    ),
    (
        "idx_session_created",
        "CREATE INDEX IF NOT EXISTS idx_session_created ON conversation_session(created_at)",
    ),
]


class FeedbackStore:
    """Thread-safe SQLite store for query logs and feedback."""

    def __init__(self, db_path: str | Path = "data/feedback.db") -> None:
        self._db_path = Path(db_path)
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            # Run migrations first so existing databases get new columns
            # before _SCHEMA tries to create indexes on them.
            self._run_migrations()
            self._conn.executescript(_SCHEMA)

    def _run_migrations(self) -> None:
        """Run schema migrations for existing databases."""
        for name, sql in _MIGRATIONS:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column/table already exists
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FeedbackStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Write operations ───────────────────────────────────────

    def log_query(self, entry: QueryLogEntry) -> QueryLogEntry:
        """Insert a query log entry."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO query_log
                   (query_id, query_hash, mode, model, input_tokens, output_tokens,
                    cost_estimate, duration_ms, source_count, error, session_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.query_id,
                    entry.query_hash,
                    entry.mode,
                    entry.model,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.cost_estimate,
                    entry.duration_ms,
                    entry.source_count,
                    entry.error,
                    entry.session_id,
                    entry.created_at,
                ),
            )
            self._conn.commit()
        return entry

    def add_feedback(self, entry: FeedbackEntry) -> FeedbackEntry:
        """Insert feedback for a query. Raises ValueError if query_id not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM query_log WHERE query_id = ?", (entry.query_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Unknown query_id: {entry.query_id}")
            self._conn.execute(
                "INSERT INTO feedback (query_id, rating, created_at) VALUES (?, ?, ?)",
                (entry.query_id, entry.rating, entry.created_at),
            )
            self._conn.commit()
        return entry

    # ── Read operations ────────────────────────────────────────

    def get_feedback(self, query_id: str) -> FeedbackEntry | None:
        """Return the latest feedback for a query, or None."""
        row = self._conn.execute(
            "SELECT query_id, rating, created_at FROM feedback WHERE query_id = ? ORDER BY id DESC LIMIT 1",
            (query_id,),
        ).fetchone()
        if not row:
            return None
        return FeedbackEntry(
            query_id=row["query_id"],
            rating=row["rating"],
            created_at=row["created_at"],
        )

    def get_daily_stats(self, days: int = 30) -> list[dict]:
        """Per-day query stats for the last N days."""
        rows = self._conn.execute(
            """SELECT
                 DATE(created_at) as day,
                 COUNT(*) as total,
                 SUM(CASE WHEN mode = 'consumer' THEN 1 ELSE 0 END) as consumer,
                 SUM(CASE WHEN mode = 'attorney' THEN 1 ELSE 0 END) as attorney,
                 AVG(cost_estimate) as avg_cost,
                 AVG(duration_ms) as avg_duration_ms
               FROM query_log
               WHERE created_at >= DATE('now', ?)
               GROUP BY DATE(created_at)
               ORDER BY day""",
            (f"-{days} days",),
        ).fetchall()
        return [
            {
                "day": row["day"],
                "total": row["total"],
                "consumer": row["consumer"],
                "attorney": row["attorney"],
                "avg_cost": round(row["avg_cost"], 6) if row["avg_cost"] else 0.0,
                "avg_duration_ms": int(row["avg_duration_ms"]) if row["avg_duration_ms"] else 0,
            }
            for row in rows
        ]

    def get_mode_distribution(self, days: int = 30) -> dict[str, int]:
        """Mode counts for the last N days."""
        rows = self._conn.execute(
            """SELECT mode, COUNT(*) as cnt
               FROM query_log
               WHERE created_at >= DATE('now', ?)
               GROUP BY mode""",
            (f"-{days} days",),
        ).fetchall()
        return {row["mode"]: row["cnt"] for row in rows}

    def get_feedback_summary(self, days: int = 30) -> dict:
        """Thumbs up/down counts and approval rate for the last N days."""
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total_feedback,
                 SUM(CASE WHEN f.rating = 1 THEN 1 ELSE 0 END) as thumbs_up,
                 SUM(CASE WHEN f.rating = -1 THEN 1 ELSE 0 END) as thumbs_down
               FROM feedback f
               JOIN query_log q ON f.query_id = q.query_id
               WHERE q.created_at >= DATE('now', ?)""",
            (f"-{days} days",),
        ).fetchone()

        total_queries_row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM query_log WHERE created_at >= DATE('now', ?)",
            (f"-{days} days",),
        ).fetchone()

        total_feedback = row["total_feedback"] or 0
        thumbs_up = row["thumbs_up"] or 0
        thumbs_down = row["thumbs_down"] or 0
        total_queries = total_queries_row["cnt"] or 0

        return {
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "total_feedback": total_feedback,
            "total_queries": total_queries,
            "approval_rate": round(thumbs_up / total_feedback, 3) if total_feedback else 0.0,
            "feedback_rate": round(total_feedback / total_queries, 3) if total_queries else 0.0,
        }

    def get_top_repeated_queries(self, days: int = 30, limit: int = 20) -> list[dict]:
        """Most-asked query hashes in the last N days."""
        rows = self._conn.execute(
            """SELECT query_hash, mode, COUNT(*) as cnt
               FROM query_log
               WHERE created_at >= DATE('now', ?)
               GROUP BY query_hash, mode
               HAVING cnt > 1
               ORDER BY cnt DESC
               LIMIT ?""",
            (f"-{days} days", limit),
        ).fetchall()
        return [
            {"query_hash": row["query_hash"], "mode": row["mode"], "count": row["cnt"]}
            for row in rows
        ]

    # ── Session operations ─────────────────────────────────────

    def create_or_update_session(
        self, session_id: str, mode: str, turn_count: int
    ) -> None:
        """Create or update a conversation session."""
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO conversation_session
                   (session_id, mode, turn_count, created_at, last_active_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     turn_count = MAX(conversation_session.turn_count, excluded.turn_count),
                     last_active_at = excluded.last_active_at""",
                (session_id, mode, turn_count, now, now),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> dict | None:
        """Get a conversation session by ID."""
        row = self._conn.execute(
            "SELECT session_id, mode, turn_count, created_at, last_active_at "
            "FROM conversation_session WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "mode": row["mode"],
            "turn_count": row["turn_count"],
            "created_at": row["created_at"],
            "last_active_at": row["last_active_at"],
        }

    def get_session_stats(self, days: int = 30) -> dict:
        """Conversation session stats for the last N days."""
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total_sessions,
                 AVG(turn_count) as avg_turns,
                 SUM(CASE WHEN mode = 'consumer' THEN 1 ELSE 0 END) as consumer,
                 SUM(CASE WHEN mode = 'attorney' THEN 1 ELSE 0 END) as attorney
               FROM conversation_session
               WHERE created_at >= DATE('now', ?)""",
            (f"-{days} days",),
        ).fetchone()
        return {
            "total_sessions": row["total_sessions"] or 0,
            "avg_turns": round(row["avg_turns"], 1) if row["avg_turns"] else 0.0,
            "consumer": row["consumer"] or 0,
            "attorney": row["attorney"] or 0,
        }
