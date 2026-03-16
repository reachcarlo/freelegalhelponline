"""Tests for P3.6 — Verify LanceDB search still works with encryption enabled.

Case file content in LanceDB must remain plaintext for FTS and vector search
to function. SQLite case data is encrypted (P3.2), but the embedding pipeline
stores chunk content in LanceDB unencrypted. This test module verifies that
the two layers coexist correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from employee_help.casefile.case_vector_store import (
    CaseChunkEmbedding,
    CaseVectorStore,
)
from employee_help.privacy.encryption import FieldEncryptor, derive_fernet_key
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseFile,
    CaseNote,
    FileType,
)
from employee_help.storage.storage import Storage

KEY = derive_fernet_key("test-secret-for-p36")
VECTOR_DIM = 768


def _make_vector(seed: float = 0.1) -> list[float]:
    """Create a dummy 768-dim vector."""
    return [seed] * VECTOR_DIM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path) -> Storage:
    db = Storage(db_path=tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture()
def enc() -> FieldEncryptor:
    return FieldEncryptor(KEY)


@pytest.fixture()
def cs(storage: Storage, enc: FieldEncryptor) -> CaseStorage:
    """CaseStorage with encryption enabled (P3.2)."""
    return CaseStorage(conn=storage._conn, encryptor=enc)


@pytest.fixture()
def cs_plain(storage: Storage) -> CaseStorage:
    """CaseStorage without encryption — for raw inspection."""
    return CaseStorage(conn=storage._conn)


@pytest.fixture()
def cvs(tmp_path: Path) -> CaseVectorStore:
    """CaseVectorStore in a temp directory."""
    return CaseVectorStore(db_path=str(tmp_path / "lancedb"))


@pytest.fixture()
def saved_case(cs: CaseStorage) -> Case:
    return cs.create_case(
        Case(name="LanceDB Test Case", user_id="u1", organization_id="org1")
    )


@pytest.fixture()
def saved_file(cs: CaseStorage, saved_case: Case) -> CaseFile:
    cf = CaseFile(
        case_id=saved_case.id,
        original_filename="employment_contract.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=2048,
        storage_path="data/test/employment_contract.pdf",
        upload_order=0,
        extracted_text="Employee shall receive overtime compensation per Labor Code § 510.",
        edited_text="Employee shall receive overtime compensation per Labor Code § 510.",
    )
    return cs.create_case_file(cf)


# ---------------------------------------------------------------------------
# SQLite encrypted, LanceDB plaintext
# ---------------------------------------------------------------------------


class TestLanceDBContentNotEncrypted:
    """Content stored in LanceDB must be plaintext for search to work."""

    def test_sqlite_has_ciphertext(self, cs_plain, saved_file, enc):
        """Precondition: SQLite text columns are encrypted."""
        raw = cs_plain._conn.execute(
            "SELECT extracted_text, edited_text FROM case_files WHERE id = ?",
            (saved_file.id,),
        ).fetchone()
        assert enc.is_encrypted(raw["extracted_text"])
        assert enc.is_encrypted(raw["edited_text"])

    def test_lancedb_stores_plaintext(self, cvs, saved_case, saved_file):
        """LanceDB content column must contain plaintext, not ciphertext."""
        content = "Employee shall receive overtime compensation per Labor Code § 510."
        emb = CaseChunkEmbedding(
            chunk_id="chunk-1",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content=content,
            heading_path="employment_contract.pdf > Page 1",
            dense_vector=_make_vector(),
            content_hash="abc123",
            is_active=True,
            file_type="pdf",
            original_filename="employment_contract.pdf",
        )
        cvs.upsert_embeddings([emb])

        # Read raw from LanceDB
        rows = cvs.table.to_arrow().to_pydict()
        assert len(rows["content"]) == 1
        stored = rows["content"][0]
        # Content should be plaintext (with heading prepended)
        assert "overtime compensation" in stored
        assert "Labor Code" in stored

    def test_lancedb_vector_search_returns_plaintext(self, cvs, saved_case, saved_file):
        """Vector search results contain plaintext content."""
        content = "Wrongful termination in violation of public policy."
        emb = CaseChunkEmbedding(
            chunk_id="chunk-2",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content=content,
            heading_path="complaint.pdf > Page 3",
            dense_vector=_make_vector(0.5),
            content_hash="def456",
            is_active=True,
            file_type="pdf",
            original_filename="complaint.pdf",
        )
        cvs.upsert_embeddings([emb])

        results = cvs.search_vector(
            case_id=saved_case.id,
            query_vector=_make_vector(0.5),
            top_k=5,
        )
        assert len(results) >= 1
        assert "Wrongful termination" in results[0]["content"]

    def test_lancedb_content_not_decryptable(self, cvs, saved_case, saved_file, enc):
        """LanceDB content should NOT look like ciphertext."""
        content = "Confidential settlement agreement terms."
        emb = CaseChunkEmbedding(
            chunk_id="chunk-3",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content=content,
            heading_path="settlement.pdf > Page 1",
            dense_vector=_make_vector(0.3),
            content_hash="ghi789",
            is_active=True,
            file_type="pdf",
            original_filename="settlement.pdf",
        )
        cvs.upsert_embeddings([emb])

        rows = cvs.table.to_arrow().to_pydict()
        for stored_content in rows["content"]:
            assert not enc.is_encrypted(stored_content)


# ---------------------------------------------------------------------------
# Dual-layer round-trip: encrypted SQLite + plaintext LanceDB
# ---------------------------------------------------------------------------


class TestDualLayerRoundTrip:
    """CaseStorage encryption and LanceDB plaintext coexist correctly."""

    def test_same_content_encrypted_in_sqlite_plain_in_lancedb(
        self, cs, cs_plain, cvs, saved_case, enc
    ):
        """Same text is encrypted in SQLite and plaintext in LanceDB."""
        content = "Plaintiff alleges wage theft under Labor Code § 203."

        # Store in SQLite via encrypted CaseStorage
        cf = cs.create_case_file(
            CaseFile(
                case_id=saved_case.id,
                original_filename="wages.pdf",
                file_type=FileType.PDF,
                mime_type="application/pdf",
                file_size_bytes=1024,
                storage_path="data/test/wages.pdf",
                upload_order=1,
                extracted_text=content,
                edited_text=content,
            )
        )

        # Store in LanceDB (simulating embedding pipeline)
        emb = CaseChunkEmbedding(
            chunk_id="chunk-dual",
            file_id=cf.id,
            case_id=saved_case.id,
            content=content,
            heading_path="wages.pdf > Page 1",
            dense_vector=_make_vector(0.7),
            content_hash="dual123",
            is_active=True,
            file_type="pdf",
            original_filename="wages.pdf",
        )
        cvs.upsert_embeddings([emb])

        # SQLite: raw DB has ciphertext
        raw = cs_plain._conn.execute(
            "SELECT extracted_text FROM case_files WHERE id = ?", (cf.id,)
        ).fetchone()
        assert enc.is_encrypted(raw["extracted_text"])
        assert "wage theft" not in raw["extracted_text"]

        # SQLite: encrypted CaseStorage decrypts correctly
        fetched = cs.get_case_file(cf.id)
        assert fetched.extracted_text == content

        # LanceDB: plaintext
        rows = cvs.table.to_arrow().to_pydict()
        lance_content = [c for c in rows["content"] if "wage theft" in c]
        assert len(lance_content) == 1

    def test_notes_encrypted_but_search_unaffected(
        self, cs, cs_plain, cvs, saved_case, enc
    ):
        """Notes are encrypted in SQLite; LanceDB doesn't store notes."""
        note = cs.create_note(
            CaseNote(
                case_id=saved_case.id,
                content="Attorney notes: potential FEHA claim, strong evidence.",
            )
        )

        # SQLite: encrypted
        raw = cs_plain._conn.execute(
            "SELECT content FROM case_notes WHERE id = ?", (note.id,)
        ).fetchone()
        assert enc.is_encrypted(raw["content"])

        # SQLite: decrypts via CaseStorage
        fetched = cs.get_note(note.id)
        assert fetched.content == "Attorney notes: potential FEHA claim, strong evidence."

        # LanceDB: notes are NOT stored there at all
        if cvs.table is not None:
            rows = cvs.table.to_arrow().to_pydict()
            for c in rows.get("content", []):
                assert "Attorney notes" not in c

    def test_multiple_files_search_isolation(self, cvs, saved_case, saved_file):
        """Multiple files in LanceDB maintain case isolation."""
        case2 = Case(name="Other Case", user_id="u2", organization_id="org2")
        # Use different case_id
        other_case_id = "other-case-id"

        emb1 = CaseChunkEmbedding(
            chunk_id="chunk-iso-1",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content="Case 1: overtime dispute evidence.",
            heading_path="doc1.pdf > Page 1",
            dense_vector=_make_vector(0.2),
            content_hash="iso1",
            is_active=True,
            file_type="pdf",
            original_filename="doc1.pdf",
        )
        emb2 = CaseChunkEmbedding(
            chunk_id="chunk-iso-2",
            file_id="other-file-id",
            case_id=other_case_id,
            content="Case 2: discrimination complaint details.",
            heading_path="doc2.pdf > Page 1",
            dense_vector=_make_vector(0.2),
            content_hash="iso2",
            is_active=True,
            file_type="pdf",
            original_filename="doc2.pdf",
        )
        cvs.upsert_embeddings([emb1, emb2])

        # Search scoped to case 1
        results = cvs.search_vector(
            case_id=saved_case.id,
            query_vector=_make_vector(0.2),
            top_k=10,
        )
        contents = [r["content"] for r in results]
        assert any("overtime dispute" in c for c in contents)
        assert not any("discrimination complaint" in c for c in contents)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEncryptionEdgeCasesLanceDB:
    def test_unicode_content_in_lancedb(self, cvs, saved_case, saved_file):
        """Unicode text stored and searchable in LanceDB."""
        content = "García v. Empleador — derechos laborales § 1102.5"
        emb = CaseChunkEmbedding(
            chunk_id="chunk-unicode",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content=content,
            heading_path="test.pdf > Page 1",
            dense_vector=_make_vector(0.4),
            content_hash="uni123",
            is_active=True,
            file_type="pdf",
            original_filename="test.pdf",
        )
        cvs.upsert_embeddings([emb])

        results = cvs.search_vector(
            case_id=saved_case.id,
            query_vector=_make_vector(0.4),
            top_k=5,
        )
        assert any("García" in r["content"] for r in results)

    def test_empty_lancedb_search_returns_empty(self, cvs, saved_case):
        """Search on empty LanceDB returns empty list, no error."""
        results = cvs.search_vector(
            case_id=saved_case.id,
            query_vector=_make_vector(),
            top_k=5,
        )
        assert results == []

    def test_delete_file_embeddings_cleans_lancedb(
        self, cvs, saved_case, saved_file
    ):
        """Deleting file embeddings removes them from LanceDB."""
        emb = CaseChunkEmbedding(
            chunk_id="chunk-del",
            file_id=saved_file.id,
            case_id=saved_case.id,
            content="Text to be deleted.",
            heading_path="delete.pdf > Page 1",
            dense_vector=_make_vector(0.6),
            content_hash="del123",
            is_active=True,
            file_type="pdf",
            original_filename="delete.pdf",
        )
        cvs.upsert_embeddings([emb])
        assert cvs.get_chunk_count(saved_case.id) == 1

        cvs.delete_file_embeddings(saved_file.id)
        assert cvs.get_chunk_count(saved_case.id) == 0
