"""Tests for P3.5 — encrypt-case-data CLI migration command.

Covers:
- Missing AUTH_JWT_SECRET → error
- Dry-run mode (reports without modifying)
- Real encryption run (plaintext → ciphertext)
- Idempotency (re-run skips already-encrypted values)
- Mixed data (some encrypted, some plaintext)
- NULL values left untouched
- Empty database (no rows)
- Data integrity (migrated data readable via CaseStorage with encryptor)
- Unicode content round-trip
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from employee_help.privacy.encryption import FieldEncryptor, derive_fernet_key
from employee_help.storage.storage import Storage


SECRET = "test-secret-p35"
KEY = derive_fernet_key(SECRET)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(db_path: str, *, dry_run: bool = False) -> SimpleNamespace:
    return SimpleNamespace(command="encrypt-case-data", dry_run=dry_run, db=db_path)


_NOW = "2026-03-15T00:00:00"


def _seed_plaintext(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Insert plaintext rows into all three tables. Returns inserted IDs."""
    import uuid

    case_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (case_id, "Test Case", "u1", "org1", "open", _NOW, _NOW),
    )

    file_ids = []
    for i, (ext, ed) in enumerate(
        [("Plain extracted 1", "Plain edited 1"), ("Plain extracted 2", None)]
    ):
        fid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, extracted_text, edited_text, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fid, case_id, f"f{i}.txt", "txt", "text/plain", 100, f"data/{i}.txt", i, ext, ed, _NOW, _NOW),
        )
        file_ids.append(fid)

    note_ids = []
    for content in ("Privileged note 1", "Privileged note 2"):
        nid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO case_notes (id, case_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (nid, case_id, content, _NOW, _NOW),
        )
        note_ids.append(nid)

    # Create a chat session first
    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO case_chat_sessions (id, case_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (session_id, case_id, _NOW, _NOW),
    )

    turn_ids = []
    for i, (role, content) in enumerate(
        [("user", "What are my rights?"), ("assistant", "Under California law...")]
    ):
        tid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO case_chat_turns (id, session_id, turn_number, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tid, session_id, i + 1, role, content, _NOW),
        )
        turn_ids.append(tid)

    conn.commit()
    return {"file_ids": file_ids, "note_ids": note_ids, "turn_ids": turn_ids}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Create a fresh DB with schema via Storage, return its path."""
    path = str(tmp_path / "test.db")
    s = Storage(db_path=path)
    s.close()
    return path


@pytest.fixture
def seeded_db(db_path: str) -> tuple[str, dict[str, list[str]]]:
    """DB with plaintext data seeded into all three tables."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ids = _seed_plaintext(conn)
    conn.close()
    return db_path, ids


@pytest.fixture
def enc() -> FieldEncryptor:
    return FieldEncryptor(KEY)


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestEncryptMigrationErrors:
    def test_missing_secret_returns_error(self, db_path, capsys):
        from employee_help.cli import _handle_encrypt_case_data

        args = _make_args(db_path)
        with patch.dict("os.environ", {}, clear=True):
            # Remove AUTH_JWT_SECRET if present
            import os
            os.environ.pop("AUTH_JWT_SECRET", None)
            result = _handle_encrypt_case_data(args)

        assert result == 1
        assert "AUTH_JWT_SECRET" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Tests: dry-run mode
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_reports_counts(self, seeded_db, capsys):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, _ = seeded_db
        args = _make_args(db_path, dry_run=True)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            result = _handle_encrypt_case_data(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "[DRY RUN]" in output
        assert "Case files encrypted: 2" in output
        assert "Case notes encrypted: 2" in output
        assert "Chat turns encrypted: 2" in output
        assert "No changes written" in output

    def test_dry_run_does_not_modify_data(self, seeded_db, enc):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, ids = seeded_db
        args = _make_args(db_path, dry_run=True)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        # Verify data is still plaintext
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT extracted_text FROM case_files WHERE id = ?", (ids["file_ids"][0],)
        ).fetchone()
        assert row["extracted_text"] == "Plain extracted 1"
        assert not enc.is_encrypted(row["extracted_text"])

        row = conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (ids["note_ids"][0],)
        ).fetchone()
        assert row["content"] == "Privileged note 1"

        row = conn.execute(
            "SELECT content FROM case_chat_turns WHERE id = ?", (ids["turn_ids"][0],)
        ).fetchone()
        assert row["content"] == "What are my rights?"
        conn.close()


# ---------------------------------------------------------------------------
# Tests: real encryption
# ---------------------------------------------------------------------------


class TestRealEncryption:
    def test_encrypts_all_plaintext(self, seeded_db, enc):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, ids = seeded_db
        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            result = _handle_encrypt_case_data(args)
        assert result == 0

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Case files
        for fid in ids["file_ids"]:
            row = conn.execute(
                "SELECT extracted_text, edited_text FROM case_files WHERE id = ?", (fid,)
            ).fetchone()
            if row["extracted_text"] is not None:
                assert enc.is_encrypted(row["extracted_text"])
            if row["edited_text"] is not None:
                assert enc.is_encrypted(row["edited_text"])

        # Case notes
        for nid in ids["note_ids"]:
            row = conn.execute(
                "SELECT content FROM case_notes WHERE id = ?", (nid,)
            ).fetchone()
            assert enc.is_encrypted(row["content"])

        # Chat turns
        for tid in ids["turn_ids"]:
            row = conn.execute(
                "SELECT content FROM case_chat_turns WHERE id = ?", (tid,)
            ).fetchone()
            assert enc.is_encrypted(row["content"])

        conn.close()

    def test_output_reports_correct_counts(self, seeded_db, capsys):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, _ = seeded_db
        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        output = capsys.readouterr().out
        assert "[DRY RUN]" not in output
        assert "Encryption migration complete." in output
        assert "Case files encrypted: 2" in output
        assert "Case notes encrypted: 2" in output
        assert "Chat turns encrypted: 2" in output
        assert "Total rows modified: 6" in output

    def test_null_values_remain_null(self, seeded_db, enc):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, ids = seeded_db
        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # file_ids[1] was seeded with edited_text=None
        row = conn.execute(
            "SELECT edited_text FROM case_files WHERE id = ?", (ids["file_ids"][1],)
        ).fetchone()
        assert row["edited_text"] is None
        conn.close()


# ---------------------------------------------------------------------------
# Tests: idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_rerun_skips_all(self, seeded_db, capsys):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, _ = seeded_db
        args = _make_args(db_path)

        # First run
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)
        capsys.readouterr()  # discard first output

        # Second run — should skip everything
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            result = _handle_encrypt_case_data(args)
        assert result == 0

        output = capsys.readouterr().out
        assert "Case files encrypted: 0" in output
        assert "Case notes encrypted: 0" in output
        assert "Chat turns encrypted: 0" in output
        assert "Already encrypted (skipped):" in output
        assert "Total rows modified: 0" in output

    def test_rerun_does_not_double_encrypt(self, seeded_db, enc):
        from employee_help.cli import _handle_encrypt_case_data

        db_path, ids = seeded_db
        args = _make_args(db_path)

        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        # Capture ciphertext after first run
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row_before = conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (ids["note_ids"][0],)
        ).fetchone()
        cipher_before = row_before["content"]
        conn.close()

        # Second run
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        # Ciphertext should still decrypt to original plaintext
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row_after = conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (ids["note_ids"][0],)
        ).fetchone()
        conn.close()

        # Values unchanged (no double encryption)
        assert row_after["content"] == cipher_before
        assert enc.decrypt(row_after["content"]) == "Privileged note 1"


# ---------------------------------------------------------------------------
# Tests: mixed data (some pre-encrypted, some plaintext)
# ---------------------------------------------------------------------------


class TestMixedData:
    def test_encrypts_only_plaintext_rows(self, db_path, enc, capsys):
        from employee_help.cli import _handle_encrypt_case_data
        import uuid

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        case_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case_id, "Mixed", "u1", "org1", "open", _NOW, _NOW),
        )

        # One pre-encrypted note, one plaintext
        pre_encrypted = enc.encrypt("Already encrypted note")
        nid_enc = str(uuid.uuid4())
        nid_plain = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO case_notes (id, case_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (nid_enc, case_id, pre_encrypted, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO case_notes (id, case_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (nid_plain, case_id, "Still plaintext", _NOW, _NOW),
        )
        conn.commit()
        conn.close()

        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        output = capsys.readouterr().out
        assert "Case notes encrypted: 1" in output
        assert "Already encrypted (skipped): 1" in output

        # Verify both decrypt correctly
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row_enc = conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (nid_enc,)
        ).fetchone()
        row_plain = conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (nid_plain,)
        ).fetchone()
        conn.close()

        assert enc.decrypt(row_enc["content"]) == "Already encrypted note"
        assert enc.is_encrypted(row_plain["content"])
        assert enc.decrypt(row_plain["content"]) == "Still plaintext"


# ---------------------------------------------------------------------------
# Tests: empty database
# ---------------------------------------------------------------------------


class TestEmptyDatabase:
    def test_empty_db_succeeds(self, db_path, capsys):
        from employee_help.cli import _handle_encrypt_case_data

        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            result = _handle_encrypt_case_data(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Total rows modified: 0" in output


# ---------------------------------------------------------------------------
# Tests: integration — migrated data readable via CaseStorage
# ---------------------------------------------------------------------------


class TestCaseStorageIntegration:
    def test_migrated_data_decryptable_via_case_storage(self, seeded_db):
        """After migration, CaseStorage with the same key should read plaintext."""
        from employee_help.cli import _handle_encrypt_case_data
        from employee_help.storage.case_storage import CaseStorage

        db_path, ids = seeded_db
        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        enc = FieldEncryptor(KEY)
        cs = CaseStorage(db_path=db_path, encryptor=enc)

        # Case file
        cf = cs.get_case_file(ids["file_ids"][0])
        assert cf.extracted_text == "Plain extracted 1"
        assert cf.edited_text == "Plain edited 1"

        # Case note
        note = cs.get_note(ids["note_ids"][0])
        assert note.content == "Privileged note 1"

        # Chat turn
        turns = cs.list_chat_turns(
            cs._conn.execute(
                "SELECT session_id FROM case_chat_turns WHERE id = ?",
                (ids["turn_ids"][0],),
            ).fetchone()["session_id"]
        )
        assert turns[0].content == "What are my rights?"
        assert turns[1].content == "Under California law..."

        cs.close()

    def test_migrated_data_without_encryptor_returns_ciphertext(self, seeded_db, enc):
        """Without encryptor, CaseStorage returns raw ciphertext (not plaintext)."""
        from employee_help.cli import _handle_encrypt_case_data
        from employee_help.storage.case_storage import CaseStorage

        db_path, ids = seeded_db
        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        cs = CaseStorage(db_path=db_path)  # No encryptor
        cf = cs.get_case_file(ids["file_ids"][0])
        # Raw ciphertext — should NOT equal plaintext
        assert cf.extracted_text != "Plain extracted 1"
        assert enc.is_encrypted(cf.extracted_text)
        cs.close()


# ---------------------------------------------------------------------------
# Tests: unicode and edge cases
# ---------------------------------------------------------------------------


class TestUnicodeAndEdgeCases:
    def test_unicode_content_survives_migration(self, db_path, enc):
        from employee_help.cli import _handle_encrypt_case_data
        import uuid

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        case_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case_id, "Unicode", "u1", "org1", "open", _NOW, _NOW),
        )
        nid = str(uuid.uuid4())
        unicode_content = "García v. Señor Employér — ¿derechos? 日本語テスト"
        conn.execute(
            "INSERT INTO case_notes (id, case_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (nid, case_id, unicode_content, _NOW, _NOW),
        )
        conn.commit()
        conn.close()

        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT content FROM case_notes WHERE id = ?", (nid,)).fetchone()
        conn.close()
        assert enc.decrypt(row["content"]) == unicode_content

    def test_empty_string_content(self, db_path, enc):
        from employee_help.cli import _handle_encrypt_case_data
        import uuid

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        case_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case_id, "Empty", "u1", "org1", "open", _NOW, _NOW),
        )
        nid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO case_notes (id, case_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (nid, case_id, "", _NOW, _NOW),
        )
        conn.commit()
        conn.close()

        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT content FROM case_notes WHERE id = ?", (nid,)).fetchone()
        conn.close()
        assert enc.is_encrypted(row["content"])
        assert enc.decrypt(row["content"]) == ""

    def test_large_text_content(self, db_path, enc):
        from employee_help.cli import _handle_encrypt_case_data
        import uuid

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        case_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case_id, "Large", "u1", "org1", "open", _NOW, _NOW),
        )
        fid = str(uuid.uuid4())
        big_text = "x" * 100_000
        conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, extracted_text, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fid, case_id, "big.txt", "txt", "text/plain", 100_000, "data/big.txt", 0, big_text, _NOW, _NOW),
        )
        conn.commit()
        conn.close()

        args = _make_args(db_path)
        with patch.dict("os.environ", {"AUTH_JWT_SECRET": SECRET}):
            _handle_encrypt_case_data(args)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT extracted_text FROM case_files WHERE id = ?", (fid,)
        ).fetchone()
        conn.close()
        assert enc.decrypt(row["extracted_text"]) == big_text
