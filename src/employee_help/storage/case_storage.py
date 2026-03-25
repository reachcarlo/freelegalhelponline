"""SQLite storage for LITIGAGENT case entities."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from employee_help.storage.models import (
    ArtifactType,
    Case,
    CaseArtifact,
    CaseChatSession,
    CaseChatTurn,
    CaseChunk,
    CaseFile,
    CaseNote,
    CaseStatus,
    FileType,
    ProcessingStatus,
)

if TYPE_CHECKING:
    from employee_help.privacy.encryption import FieldEncryptor


class CaseStorage:
    """CRUD operations for cases, case files, notes, and chunks.

    Operates on the same SQLite database as the knowledge-base Storage class.
    Accepts either a raw sqlite3.Connection or a db_path.

    When an *encryptor* is provided, sensitive text columns
    (``extracted_text``, ``edited_text``, ``content`` on notes and chat turns)
    are transparently encrypted on write and decrypted on read.
    """

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        db_path: str | Path | None = None,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self._enc = encryptor
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

    def __enter__(self) -> CaseStorage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Encryption helpers ─────────────────────────────────────

    def _encrypt(self, text: str | None) -> str | None:
        """Encrypt a value if an encryptor is configured, otherwise pass through."""
        return self._enc.encrypt(text) if self._enc else text

    def _decrypt(self, text: str | None) -> str | None:
        """Decrypt a value if an encryptor is configured, otherwise pass through."""
        return self._enc.decrypt(text) if self._enc else text

    # ── Cases ──────────────────────────────────────────────────

    def create_case(self, case: Case) -> Case:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """INSERT INTO cases (id, name, user_id, organization_id,
               description, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                case.id,
                case.name,
                case.user_id,
                case.organization_id,
                case.description,
                case.status.value,
                now,
                now,
            ),
        )
        self._conn.commit()
        case.created_at = datetime.fromisoformat(now)
        case.updated_at = datetime.fromisoformat(now)
        return case

    def get_case(
        self, case_id: str, *, user_id: str | None = None
    ) -> Case | None:
        if user_id is not None:
            row = self._conn.execute(
                "SELECT * FROM cases WHERE id = ? AND user_id = ?",
                (case_id, user_id),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_case(row)

    def list_cases(
        self, *, user_id: str, status: CaseStatus | None = None
    ) -> list[Case]:
        if status is not None:
            rows = self._conn.execute(
                "SELECT * FROM cases WHERE user_id = ? AND status = ? "
                "ORDER BY updated_at DESC",
                (user_id, status.value),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cases WHERE user_id = ? "
                "ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._row_to_case(row) for row in rows]

    def update_case(
        self,
        case_id: str,
        *,
        name: str | None = None,
        description: str | None = ...,  # type: ignore[assignment]
        user_id: str | None = None,
    ) -> Case | None:
        case = self.get_case(case_id)
        if not case:
            return None
        if name is not None:
            case.name = name
        if description is not ...:
            case.description = description
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            "UPDATE cases SET name = ?, description = ?, "
            "updated_at = ? WHERE id = ?",
            (case.name, case.description, now, case_id),
        )
        self._conn.commit()
        case.updated_at = datetime.fromisoformat(now)
        return case

    def archive_case(
        self, case_id: str, *, user_id: str | None = None
    ) -> bool:
        now = datetime.now(tz=UTC).isoformat()
        if user_id is not None:
            cur = self._conn.execute(
                "UPDATE cases SET status = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?",
                (CaseStatus.ARCHIVED.value, now, case_id, user_id),
            )
        else:
            cur = self._conn.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
                (CaseStatus.ARCHIVED.value, now, case_id),
            )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_case(
        self, case_id: str, *, user_id: str | None = None
    ) -> bool:
        if user_id is not None:
            cur = self._conn.execute(
                "DELETE FROM cases WHERE id = ? AND user_id = ?",
                (case_id, user_id),
            )
        else:
            cur = self._conn.execute(
                "DELETE FROM cases WHERE id = ?", (case_id,)
            )
        self._conn.commit()
        return cur.rowcount > 0

    # ── Case Files ─────────────────────────────────────────────

    def create_case_file(self, case_file: CaseFile) -> CaseFile:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """INSERT INTO case_files
               (id, case_id, original_filename, file_type, mime_type,
                file_size_bytes, storage_path, upload_order,
                processing_status, error_message, extracted_text,
                edited_text, text_dirty, ocr_confidence, page_count,
                metadata, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                case_file.id,
                case_file.case_id,
                case_file.original_filename,
                case_file.file_type.value,
                case_file.mime_type,
                case_file.file_size_bytes,
                case_file.storage_path,
                case_file.upload_order,
                case_file.processing_status.value,
                case_file.error_message,
                self._encrypt(case_file.extracted_text),
                self._encrypt(case_file.edited_text),
                1 if case_file.text_dirty else 0,
                case_file.ocr_confidence,
                case_file.page_count,
                json.dumps(case_file.metadata) if case_file.metadata else None,
                case_file.content_hash,
                now,
                now,
            ),
        )
        self._conn.commit()
        case_file.created_at = datetime.fromisoformat(now)
        case_file.updated_at = datetime.fromisoformat(now)
        return case_file

    def get_case_file(self, file_id: str) -> CaseFile | None:
        row = self._conn.execute(
            "SELECT * FROM case_files WHERE id = ?", (file_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_case_file(row)

    def list_case_files(self, case_id: str) -> list[CaseFile]:
        rows = self._conn.execute(
            "SELECT * FROM case_files WHERE case_id = ? ORDER BY upload_order",
            (case_id,),
        ).fetchall()
        return [self._row_to_case_file(row) for row in rows]

    def update_case_file_status(
        self,
        file_id: str,
        status: ProcessingStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """UPDATE case_files
               SET processing_status = ?, error_message = ?, updated_at = ?
               WHERE id = ?""",
            (status.value, error_message, now, file_id),
        )
        self._conn.commit()

    def update_case_file_text(
        self,
        file_id: str,
        *,
        extracted_text: str | None = None,
        edited_text: str | None = None,
        ocr_confidence: float | None = None,
        page_count: int | None = None,
        content_hash: str | None = None,
        metadata: dict | None = None,
    ) -> CaseFile | None:
        cf = self.get_case_file(file_id)
        if not cf:
            return None
        if extracted_text is not None:
            cf.extracted_text = extracted_text
            if cf.edited_text is None:
                cf.edited_text = extracted_text
        if edited_text is not None:
            cf.edited_text = edited_text
        cf.text_dirty = cf.extracted_text != cf.edited_text
        if ocr_confidence is not None:
            cf.ocr_confidence = ocr_confidence
        if page_count is not None:
            cf.page_count = page_count
        if content_hash is not None:
            cf.content_hash = content_hash
        if metadata is not None:
            cf.metadata = metadata
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """UPDATE case_files
               SET extracted_text = ?, edited_text = ?, text_dirty = ?,
                   ocr_confidence = ?, page_count = ?, content_hash = ?,
                   metadata = ?, updated_at = ?
               WHERE id = ?""",
            (
                self._encrypt(cf.extracted_text),
                self._encrypt(cf.edited_text),
                1 if cf.text_dirty else 0,
                cf.ocr_confidence,
                cf.page_count,
                cf.content_hash,
                json.dumps(cf.metadata) if cf.metadata else None,
                now,
                file_id,
            ),
        )
        self._conn.commit()
        cf.updated_at = datetime.fromisoformat(now)
        return cf

    def delete_case_file(self, file_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM case_files WHERE id = ?", (file_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_next_upload_order(self, case_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(upload_order), -1) + 1 AS next_order FROM case_files WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        return row["next_order"]

    # ── Case Notes ─────────────────────────────────────────────

    def create_note(self, note: CaseNote) -> CaseNote:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """INSERT INTO case_notes (id, case_id, file_id, content, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (note.id, note.case_id, note.file_id, self._encrypt(note.content), now, now),
        )
        self._conn.commit()
        note.created_at = datetime.fromisoformat(now)
        note.updated_at = datetime.fromisoformat(now)
        return note

    def get_note(self, note_id: str) -> CaseNote | None:
        row = self._conn.execute(
            "SELECT * FROM case_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_case_note(row)

    def list_notes(
        self, case_id: str, *, file_id: str | None = None
    ) -> list[CaseNote]:
        if file_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM case_notes WHERE case_id = ? AND file_id = ? ORDER BY created_at",
                (case_id, file_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            ).fetchall()
        return [self._row_to_case_note(row) for row in rows]

    def update_note(self, note_id: str, content: str) -> CaseNote | None:
        note = self.get_note(note_id)
        if not note:
            return None
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            "UPDATE case_notes SET content = ?, updated_at = ? WHERE id = ?",
            (self._encrypt(content), now, note_id),
        )
        self._conn.commit()
        note.content = content
        note.updated_at = datetime.fromisoformat(now)
        return note

    def delete_note(self, note_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM case_notes WHERE id = ?", (note_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Case Chunks ────────────────────────────────────────────

    def insert_case_chunks(self, chunks: list[CaseChunk]) -> None:
        self._conn.executemany(
            """INSERT INTO case_chunks
               (id, file_id, case_id, chunk_index, content,
                heading_path, token_count, content_hash, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    c.id,
                    c.file_id,
                    c.case_id,
                    c.chunk_index,
                    c.content,
                    c.heading_path,
                    c.token_count,
                    c.content_hash,
                    1 if c.is_active else 0,
                    c.created_at.isoformat(),
                )
                for c in chunks
            ],
        )
        self._conn.commit()

    def get_case_chunks(
        self,
        case_id: str | None = None,
        file_id: str | None = None,
    ) -> list[CaseChunk]:
        if file_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM case_chunks WHERE file_id = ? AND is_active = 1 ORDER BY chunk_index",
                (file_id,),
            ).fetchall()
        elif case_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM case_chunks WHERE case_id = ? AND is_active = 1 ORDER BY file_id, chunk_index",
                (case_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM case_chunks WHERE is_active = 1 ORDER BY case_id, file_id, chunk_index"
            ).fetchall()
        return [self._row_to_case_chunk(row) for row in rows]

    def delete_case_chunks_for_file(self, file_id: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM case_chunks WHERE file_id = ?", (file_id,)
        )
        self._conn.commit()
        return cur.rowcount

    def get_case_chunk_count(self, case_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM case_chunks WHERE case_id = ? AND is_active = 1",
            (case_id,),
        ).fetchone()
        return row["cnt"]

    # ── Chat Sessions & Turns ─────────────────────────────────

    def create_chat_session(self, session: CaseChatSession) -> CaseChatSession:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """INSERT INTO case_chat_sessions (id, case_id, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (session.id, session.case_id, now, now),
        )
        self._conn.commit()
        session.created_at = datetime.fromisoformat(now)
        session.updated_at = datetime.fromisoformat(now)
        return session

    def get_chat_session(self, session_id: str) -> CaseChatSession | None:
        row = self._conn.execute(
            "SELECT * FROM case_chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_chat_session(row)

    def list_chat_sessions(self, case_id: str) -> list[CaseChatSession]:
        rows = self._conn.execute(
            "SELECT * FROM case_chat_sessions WHERE case_id = ? ORDER BY updated_at DESC",
            (case_id,),
        ).fetchall()
        return [self._row_to_chat_session(row) for row in rows]

    def update_chat_session_timestamp(self, session_id: str) -> None:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            "UPDATE case_chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self._conn.commit()

    def delete_chat_session(self, session_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM case_chat_sessions WHERE id = ?", (session_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def create_chat_turn(self, turn: CaseChatTurn) -> CaseChatTurn:
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            """INSERT INTO case_chat_turns
               (id, session_id, turn_number, role, content, sources, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                turn.id,
                turn.session_id,
                turn.turn_number,
                turn.role,
                self._encrypt(turn.content),
                turn.sources,
                now,
            ),
        )
        self._conn.commit()
        turn.created_at = datetime.fromisoformat(now)
        return turn

    def list_chat_turns(self, session_id: str) -> list[CaseChatTurn]:
        rows = self._conn.execute(
            "SELECT * FROM case_chat_turns WHERE session_id = ? ORDER BY turn_number",
            (session_id,),
        ).fetchall()
        return [self._row_to_chat_turn(row) for row in rows]

    def get_chat_session_turn_count(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM case_chat_turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["cnt"]

    # ── Private helpers ────────────────────────────────────────

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> Case:
        return Case(
            id=row["id"],
            name=row["name"],
            user_id=row["user_id"],
            organization_id=row["organization_id"],
            description=row["description"],
            status=CaseStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_case_file(self, row: sqlite3.Row) -> CaseFile:
        meta = row["metadata"]
        return CaseFile(
            id=row["id"],
            case_id=row["case_id"],
            original_filename=row["original_filename"],
            file_type=FileType(row["file_type"]),
            mime_type=row["mime_type"],
            file_size_bytes=row["file_size_bytes"],
            storage_path=row["storage_path"],
            upload_order=row["upload_order"],
            processing_status=ProcessingStatus(row["processing_status"]),
            error_message=row["error_message"],
            extracted_text=self._decrypt(row["extracted_text"]),
            edited_text=self._decrypt(row["edited_text"]),
            text_dirty=bool(row["text_dirty"]),
            ocr_confidence=row["ocr_confidence"],
            page_count=row["page_count"],
            metadata=json.loads(meta) if meta else None,
            content_hash=row["content_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_case_note(self, row: sqlite3.Row) -> CaseNote:
        return CaseNote(
            id=row["id"],
            case_id=row["case_id"],
            file_id=row["file_id"],
            content=self._decrypt(row["content"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_case_chunk(row: sqlite3.Row) -> CaseChunk:
        return CaseChunk(
            id=row["id"],
            file_id=row["file_id"],
            case_id=row["case_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            heading_path=row["heading_path"],
            token_count=row["token_count"],
            content_hash=row["content_hash"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_chat_session(row: sqlite3.Row) -> CaseChatSession:
        return CaseChatSession(
            id=row["id"],
            case_id=row["case_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_chat_turn(self, row: sqlite3.Row) -> CaseChatTurn:
        return CaseChatTurn(
            id=row["id"],
            session_id=row["session_id"],
            turn_number=row["turn_number"],
            role=row["role"],
            content=self._decrypt(row["content"]),
            sources=row["sources"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ── Artifacts ──────────────────────────────────────────────────

    def create_artifact(self, artifact: CaseArtifact) -> CaseArtifact:
        now = datetime.now(tz=UTC).isoformat()
        meta_json = json.dumps(artifact.metadata) if artifact.metadata else None
        self._conn.execute(
            """INSERT INTO case_artifacts
               (id, case_id, artifact_type, tool_source, summary, file_path, metadata, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                artifact.id,
                artifact.case_id,
                artifact.artifact_type.value if isinstance(artifact.artifact_type, ArtifactType) else artifact.artifact_type,
                artifact.tool_source,
                artifact.summary,
                artifact.file_path,
                meta_json,
                now,
                artifact.created_by,
            ),
        )
        self._conn.commit()
        artifact.created_at = datetime.fromisoformat(now)
        return artifact

    def list_artifacts(self, case_id: str) -> list[CaseArtifact]:
        rows = self._conn.execute(
            "SELECT * FROM case_artifacts WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def get_artifact(self, artifact_id: str) -> CaseArtifact | None:
        row = self._conn.execute(
            "SELECT * FROM case_artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        return self._row_to_artifact(row) if row else None

    def delete_artifact(self, artifact_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM case_artifacts WHERE id = ?", (artifact_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> CaseArtifact:
        meta = json.loads(row["metadata"]) if row["metadata"] else None
        return CaseArtifact(
            id=row["id"],
            case_id=row["case_id"],
            artifact_type=ArtifactType(row["artifact_type"]),
            tool_source=row["tool_source"],
            summary=row["summary"],
            file_path=row["file_path"],
            metadata=meta,
            created_at=datetime.fromisoformat(row["created_at"]),
            created_by=row["created_by"],
        )
