"""SQLite storage for LITIGAGENTv2 case facts. Append-only semantics."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


class CaseFactStorage:
    """CRUD for the case_facts table. Append-only semantics."""

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
            self._conn = sqlite3.connect(str(p))
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

    def __enter__(self) -> CaseFactStorage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Facts ──────────────────────────────────────────────────

    def add_fact(self, fact: CaseFact) -> CaseFact:
        """Insert a new fact. Returns the fact with generated ID."""
        self._conn.execute(
            """INSERT INTO case_facts
               (id, case_id, category, fact_type, value,
                source_file_id, extraction_method, confidence,
                confirmed, superseded_by, effective_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.id,
                fact.case_id,
                fact.category.value,
                fact.fact_type,
                json.dumps(fact.value),
                fact.source_file_id,
                fact.extraction_method.value,
                fact.confidence,
                1 if fact.confirmed else 0,
                fact.superseded_by,
                fact.effective_date,
                fact.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return fact

    def supersede(self, old_fact_id: str, new_fact: CaseFact) -> CaseFact:
        """Create new_fact and set old_fact.superseded_by = new_fact.id.

        Atomic (single transaction).
        """
        self._conn.execute(
            """INSERT INTO case_facts
               (id, case_id, category, fact_type, value,
                source_file_id, extraction_method, confidence,
                confirmed, superseded_by, effective_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_fact.id,
                new_fact.case_id,
                new_fact.category.value,
                new_fact.fact_type,
                json.dumps(new_fact.value),
                new_fact.source_file_id,
                new_fact.extraction_method.value,
                new_fact.confidence,
                1 if new_fact.confirmed else 0,
                new_fact.superseded_by,
                new_fact.effective_date,
                new_fact.created_at.isoformat(),
            ),
        )
        self._conn.execute(
            "UPDATE case_facts SET superseded_by = ? WHERE id = ?",
            (new_fact.id, old_fact_id),
        )
        self._conn.commit()
        return new_fact

    def confirm(self, fact_id: str) -> None:
        """Set confirmed = True on a fact. The only mutation allowed."""
        self._conn.execute(
            "UPDATE case_facts SET confirmed = 1 WHERE id = ?",
            (fact_id,),
        )
        self._conn.commit()

    def list_current_facts(
        self, case_id: str, category: str | None = None
    ) -> list[CaseFact]:
        """All facts WHERE superseded_by IS NULL, optionally filtered by category."""
        if category is not None:
            rows = self._conn.execute(
                "SELECT * FROM case_facts WHERE case_id = ? AND category = ? "
                "AND superseded_by IS NULL ORDER BY created_at",
                (case_id, category),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM case_facts WHERE case_id = ? "
                "AND superseded_by IS NULL ORDER BY created_at",
                (case_id,),
            ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def list_all_facts(
        self, case_id: str, category: str | None = None
    ) -> list[CaseFact]:
        """All facts including superseded (for history view)."""
        if category is not None:
            rows = self._conn.execute(
                "SELECT * FROM case_facts WHERE case_id = ? AND category = ? "
                "ORDER BY created_at",
                (case_id, category),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM case_facts WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def list_facts_for_file(self, file_id: str) -> list[CaseFact]:
        """All facts extracted from a specific file."""
        rows = self._conn.execute(
            "SELECT * FROM case_facts WHERE source_file_id = ? ORDER BY created_at",
            (file_id,),
        ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def delete_facts_for_file(self, file_id: str) -> int:
        """Remove all facts sourced from a file (when file is deleted or re-processed)."""
        cur = self._conn.execute(
            "DELETE FROM case_facts WHERE source_file_id = ?",
            (file_id,),
        )
        self._conn.commit()
        return cur.rowcount

    def fact_count(self, case_id: str) -> tuple[int, int]:
        """Returns (total_current, confirmed_current)."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN confirmed = 1 THEN 1 ELSE 0 END) AS confirmed "
            "FROM case_facts WHERE case_id = ? AND superseded_by IS NULL",
            (case_id,),
        ).fetchone()
        return (row["total"], row["confirmed"] or 0)

    # ── Private helpers ────────────────────────────────────────

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> CaseFact:
        return CaseFact(
            id=row["id"],
            case_id=row["case_id"],
            category=FactCategory(row["category"]),
            fact_type=row["fact_type"],
            value=json.loads(row["value"]),
            source_file_id=row["source_file_id"],
            extraction_method=ExtractionMethod(row["extraction_method"]),
            confidence=row["confidence"],
            confirmed=bool(row["confirmed"]),
            superseded_by=row["superseded_by"],
            effective_date=row["effective_date"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
