"""Tests for P3.2 — CaseStorage encryption integration.

Verifies that sensitive text columns (extracted_text, edited_text, note content,
chat turn content) are encrypted at rest and decrypted on read when a
FieldEncryptor is provided to CaseStorage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from employee_help.privacy.encryption import FieldEncryptor, derive_fernet_key
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseChatSession,
    CaseChatTurn,
    CaseFile,
    CaseNote,
    FileType,
)
from employee_help.storage.storage import Storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KEY = derive_fernet_key("test-secret-for-p32")


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db = Storage(db_path=tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def enc() -> FieldEncryptor:
    return FieldEncryptor(KEY)


@pytest.fixture
def cs(storage: Storage, enc: FieldEncryptor) -> CaseStorage:
    """CaseStorage with encryption enabled."""
    return CaseStorage(conn=storage._conn, encryptor=enc)


@pytest.fixture
def cs_plain(storage: Storage) -> CaseStorage:
    """CaseStorage without encryption — for raw DB inspection."""
    return CaseStorage(conn=storage._conn)


@pytest.fixture
def saved_case(cs: CaseStorage) -> Case:
    return cs.create_case(
        Case(name="Test Case", user_id="u1", organization_id="org1")
    )


@pytest.fixture
def saved_file(cs: CaseStorage, saved_case: Case) -> CaseFile:
    cf = CaseFile(
        case_id=saved_case.id,
        original_filename="doc.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_path="data/test/doc.pdf",
        upload_order=0,
        extracted_text="Sensitive extracted content",
        edited_text="Sensitive edited content",
    )
    return cs.create_case_file(cf)


# ---------------------------------------------------------------------------
# CaseFile encryption
# ---------------------------------------------------------------------------


class TestCaseFileEncryption:
    def test_extracted_text_encrypted_at_rest(self, cs, cs_plain, saved_file, enc):
        """Raw DB should contain ciphertext, not plaintext."""
        raw = cs_plain._conn.execute(
            "SELECT extracted_text FROM case_files WHERE id = ?",
            (saved_file.id,),
        ).fetchone()
        raw_text = raw["extracted_text"]
        assert raw_text != "Sensitive extracted content"
        assert enc.is_encrypted(raw_text)

    def test_edited_text_encrypted_at_rest(self, cs, cs_plain, saved_file, enc):
        raw = cs_plain._conn.execute(
            "SELECT edited_text FROM case_files WHERE id = ?",
            (saved_file.id,),
        ).fetchone()
        raw_text = raw["edited_text"]
        assert raw_text != "Sensitive edited content"
        assert enc.is_encrypted(raw_text)

    def test_get_case_file_decrypts(self, cs, saved_file):
        """get_case_file should return plaintext."""
        cf = cs.get_case_file(saved_file.id)
        assert cf.extracted_text == "Sensitive extracted content"
        assert cf.edited_text == "Sensitive edited content"

    def test_list_case_files_decrypts(self, cs, saved_file):
        files = cs.list_case_files(saved_file.case_id)
        assert len(files) == 1
        assert files[0].extracted_text == "Sensitive extracted content"

    def test_update_case_file_text_encrypts(self, cs, cs_plain, saved_file, enc):
        cs.update_case_file_text(
            saved_file.id,
            extracted_text="New extracted",
            edited_text="New edited",
        )
        # Verify raw DB has ciphertext
        raw = cs_plain._conn.execute(
            "SELECT extracted_text, edited_text FROM case_files WHERE id = ?",
            (saved_file.id,),
        ).fetchone()
        assert raw["extracted_text"] != "New extracted"
        assert raw["edited_text"] != "New edited"
        assert enc.is_encrypted(raw["extracted_text"])
        assert enc.is_encrypted(raw["edited_text"])
        # Verify read decrypts
        cf = cs.get_case_file(saved_file.id)
        assert cf.extracted_text == "New extracted"
        assert cf.edited_text == "New edited"

    def test_null_text_not_encrypted(self, cs, saved_case):
        """None values should remain NULL, not encrypted."""
        cf = CaseFile(
            case_id=saved_case.id,
            original_filename="empty.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=0,
            storage_path="data/test/empty.txt",
            upload_order=1,
        )
        saved = cs.create_case_file(cf)
        raw = cs._conn.execute(
            "SELECT extracted_text, edited_text FROM case_files WHERE id = ?",
            (saved.id,),
        ).fetchone()
        assert raw["extracted_text"] is None
        assert raw["edited_text"] is None

    def test_text_dirty_flag_correct_with_encryption(self, cs, saved_case):
        """text_dirty should compare plaintext, not ciphertext."""
        cf = CaseFile(
            case_id=saved_case.id,
            original_filename="test.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=100,
            storage_path="data/test/test.txt",
            upload_order=1,
            extracted_text="original text",
            edited_text="original text",
        )
        saved = cs.create_case_file(cf)
        assert not saved.text_dirty

        # Update edited_text to differ
        updated = cs.update_case_file_text(
            saved.id, edited_text="modified text"
        )
        assert updated.text_dirty is True

        # Update edited_text back to match extracted
        updated2 = cs.update_case_file_text(
            saved.id, edited_text="original text"
        )
        assert updated2.text_dirty is False


# ---------------------------------------------------------------------------
# CaseNote encryption
# ---------------------------------------------------------------------------


class TestCaseNoteEncryption:
    def test_note_content_encrypted_at_rest(self, cs, cs_plain, saved_case, enc):
        note = cs.create_note(
            CaseNote(case_id=saved_case.id, content="Privileged attorney notes")
        )
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (note.id,)
        ).fetchone()
        assert raw["content"] != "Privileged attorney notes"
        assert enc.is_encrypted(raw["content"])

    def test_get_note_decrypts(self, cs, saved_case):
        note = cs.create_note(
            CaseNote(case_id=saved_case.id, content="Secret note")
        )
        fetched = cs.get_note(note.id)
        assert fetched.content == "Secret note"

    def test_list_notes_decrypts(self, cs, saved_case):
        cs.create_note(CaseNote(case_id=saved_case.id, content="Note 1"))
        cs.create_note(CaseNote(case_id=saved_case.id, content="Note 2"))
        notes = cs.list_notes(saved_case.id)
        assert [n.content for n in notes] == ["Note 1", "Note 2"]

    def test_update_note_encrypts(self, cs, cs_plain, saved_case, enc):
        note = cs.create_note(
            CaseNote(case_id=saved_case.id, content="Original")
        )
        cs.update_note(note.id, "Updated content")
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (note.id,)
        ).fetchone()
        assert raw["content"] != "Updated content"
        assert enc.is_encrypted(raw["content"])
        # Read back decrypted
        fetched = cs.get_note(note.id)
        assert fetched.content == "Updated content"


# ---------------------------------------------------------------------------
# CaseChatTurn encryption
# ---------------------------------------------------------------------------


class TestChatTurnEncryption:
    @pytest.fixture
    def session(self, cs, saved_case):
        return cs.create_chat_session(
            CaseChatSession(case_id=saved_case.id)
        )

    def test_chat_turn_content_encrypted_at_rest(self, cs, cs_plain, session, enc):
        turn = cs.create_chat_turn(
            CaseChatTurn(
                session_id=session.id,
                turn_number=1,
                role="user",
                content="What are my rights?",
            )
        )
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_chat_turns WHERE id = ?", (turn.id,)
        ).fetchone()
        assert raw["content"] != "What are my rights?"
        assert enc.is_encrypted(raw["content"])

    def test_list_chat_turns_decrypts(self, cs, session):
        cs.create_chat_turn(
            CaseChatTurn(
                session_id=session.id, turn_number=1, role="user", content="Q1"
            )
        )
        cs.create_chat_turn(
            CaseChatTurn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                content="A1",
            )
        )
        turns = cs.list_chat_turns(session.id)
        assert [t.content for t in turns] == ["Q1", "A1"]

    def test_sources_not_encrypted(self, cs, cs_plain, session):
        """sources is metadata, not privileged — should stay plaintext."""
        turn = cs.create_chat_turn(
            CaseChatTurn(
                session_id=session.id,
                turn_number=1,
                role="assistant",
                content="Answer",
                sources='[{"file": "doc.pdf"}]',
            )
        )
        raw = cs_plain._conn.execute(
            "SELECT sources FROM case_chat_turns WHERE id = ?", (turn.id,)
        ).fetchone()
        assert raw["sources"] == '[{"file": "doc.pdf"}]'


# ---------------------------------------------------------------------------
# No-encryptor passthrough
# ---------------------------------------------------------------------------


class TestNoEncryptorPassthrough:
    """When no encryptor is provided, data is stored as plaintext (backward compat)."""

    def test_case_file_plaintext_without_encryptor(self, cs_plain, storage):
        case = cs_plain.create_case(
            Case(name="Plain Case", user_id="u1", organization_id="org1")
        )
        cf = cs_plain.create_case_file(
            CaseFile(
                case_id=case.id,
                original_filename="plain.txt",
                file_type=FileType.TXT,
                mime_type="text/plain",
                file_size_bytes=100,
                storage_path="data/test/plain.txt",
                upload_order=0,
                extracted_text="Unencrypted text",
            )
        )
        raw = cs_plain._conn.execute(
            "SELECT extracted_text FROM case_files WHERE id = ?", (cf.id,)
        ).fetchone()
        assert raw["extracted_text"] == "Unencrypted text"

    def test_note_plaintext_without_encryptor(self, cs_plain, storage):
        case = cs_plain.create_case(
            Case(name="Plain Case", user_id="u1", organization_id="org1")
        )
        note = cs_plain.create_note(
            CaseNote(case_id=case.id, content="Unencrypted note")
        )
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (note.id,)
        ).fetchone()
        assert raw["content"] == "Unencrypted note"

    def test_chat_turn_plaintext_without_encryptor(self, cs_plain, storage):
        case = cs_plain.create_case(
            Case(name="Plain Case", user_id="u1", organization_id="org1")
        )
        session = cs_plain.create_chat_session(
            CaseChatSession(case_id=case.id)
        )
        turn = cs_plain.create_chat_turn(
            CaseChatTurn(
                session_id=session.id,
                turn_number=1,
                role="user",
                content="Unencrypted turn",
            )
        )
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_chat_turns WHERE id = ?", (turn.id,)
        ).fetchone()
        assert raw["content"] == "Unencrypted turn"


# ---------------------------------------------------------------------------
# Unicode & edge cases
# ---------------------------------------------------------------------------


class TestEncryptionEdgeCases:
    def test_unicode_round_trip(self, cs, saved_case):
        note = cs.create_note(
            CaseNote(
                case_id=saved_case.id,
                content="García v. Señor Employér — ¿derechos?",
            )
        )
        fetched = cs.get_note(note.id)
        assert fetched.content == "García v. Señor Employér — ¿derechos?"

    def test_empty_string_round_trip(self, cs, saved_case):
        note = cs.create_note(
            CaseNote(case_id=saved_case.id, content="")
        )
        fetched = cs.get_note(note.id)
        assert fetched.content == ""

    def test_large_text_round_trip(self, cs, saved_case):
        big_text = "x" * 100_000
        cf = CaseFile(
            case_id=saved_case.id,
            original_filename="big.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=100_000,
            storage_path="data/test/big.txt",
            upload_order=1,
            extracted_text=big_text,
        )
        saved = cs.create_case_file(cf)
        fetched = cs.get_case_file(saved.id)
        assert fetched.extracted_text == big_text
