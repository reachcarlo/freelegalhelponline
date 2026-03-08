"""Tests for CaseVectorStore and case file embedding pipeline (L3.2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.case_vector_store import (
    CaseChunkEmbedding,
    CaseVectorStore,
)
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import Case, CaseFile, FileType, ProcessingStatus
from employee_help.storage.storage import Storage


@pytest.fixture()
def db():
    """In-memory SQLite database with schema."""
    storage = Storage(db_path=":memory:")
    yield storage._conn
    storage.close()


@pytest.fixture()
def case_storage(db):
    """CaseStorage backed by in-memory DB."""
    return CaseStorage(conn=db)


# --- CaseChunkEmbedding dataclass ---


class TestCaseChunkEmbedding:
    def test_create(self):
        emb = CaseChunkEmbedding(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="Hello world",
            heading_path="test.pdf > Page 1",
            dense_vector=[0.1] * 768,
            content_hash="abc123",
            is_active=True,
            file_type="pdf",
            original_filename="test.pdf",
        )
        assert emb.chunk_id == "c1"
        assert emb.case_id == "case1"
        assert len(emb.dense_vector) == 768

    def test_fields(self):
        emb = CaseChunkEmbedding(
            chunk_id="c2",
            file_id="f2",
            case_id="case2",
            content="Some text",
            heading_path="doc.docx",
            dense_vector=[0.0],
            content_hash="def456",
            is_active=False,
            file_type="docx",
            original_filename="doc.docx",
        )
        assert emb.is_active is False
        assert emb.file_type == "docx"


# --- CaseVectorStore ---


class TestCaseVectorStoreInit:
    def test_table_name(self):
        store = CaseVectorStore(db_path="/tmp/test_lance")
        assert store.TABLE_NAME == "case_embeddings"

    def test_db_path(self):
        store = CaseVectorStore(db_path="/tmp/custom_path")
        assert store.db_path == "/tmp/custom_path"

    def test_default_db_path(self):
        store = CaseVectorStore()
        assert store.db_path == "data/lancedb"


class TestCaseVectorStoreRecords:
    def test_to_records(self):
        store = CaseVectorStore()
        emb = CaseChunkEmbedding(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="Hello world",
            heading_path="test.pdf > Page 1",
            dense_vector=[0.1, 0.2, 0.3],
            content_hash="abc123",
            is_active=True,
            file_type="pdf",
            original_filename="test.pdf",
        )
        records = store._to_records([emb])

        assert len(records) == 1
        r = records[0]
        assert r["chunk_id"] == "c1"
        assert r["file_id"] == "f1"
        assert r["case_id"] == "case1"
        assert r["vector"] == [0.1, 0.2, 0.3]
        assert r["content_hash"] == "abc123"
        assert r["is_active"] is True
        assert r["file_type"] == "pdf"
        assert r["original_filename"] == "test.pdf"

    def test_to_records_prepends_heading_to_content(self):
        store = CaseVectorStore()
        emb = CaseChunkEmbedding(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="Body text",
            heading_path="test.pdf > Page 1",
            dense_vector=[0.1],
            content_hash="abc",
            is_active=True,
            file_type="pdf",
            original_filename="test.pdf",
        )
        records = store._to_records([emb])
        assert records[0]["content"] == "test.pdf > Page 1\nBody text"

    def test_to_records_empty_heading(self):
        store = CaseVectorStore()
        emb = CaseChunkEmbedding(
            chunk_id="c1",
            file_id="f1",
            case_id="case1",
            content="Body only",
            heading_path="",
            dense_vector=[0.1],
            content_hash="abc",
            is_active=True,
            file_type="txt",
            original_filename="notes.txt",
        )
        records = store._to_records([emb])
        assert records[0]["content"] == "Body only"

    def test_to_records_empty_list(self):
        store = CaseVectorStore()
        assert store._to_records([]) == []


class TestCaseVectorStoreNoTable:
    """Test methods when no table exists."""

    def test_table_is_none_initially(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        assert store.table is None

    def test_search_hybrid_returns_empty(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        result = store.search_hybrid("case1", "query", [0.1] * 768)
        assert result == []

    def test_search_vector_returns_empty(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        result = store.search_vector("case1", [0.1] * 768)
        assert result == []

    def test_get_chunk_count_returns_zero(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        assert store.get_chunk_count("case1") == 0

    def test_delete_file_embeddings_noop(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        # Should not raise
        store.delete_file_embeddings("f1")

    def test_delete_case_embeddings_noop(self):
        store = CaseVectorStore()
        store._db = MagicMock()
        store._db.table_names.return_value = []
        store.delete_case_embeddings("case1")

    def test_upsert_empty_list_noop(self):
        store = CaseVectorStore()
        store.upsert_embeddings([])


@pytest.mark.slow
class TestCaseVectorStoreLanceDB:
    """Integration tests using real LanceDB (tmp directory)."""

    def _make_embedding(
        self,
        chunk_id: str = "c1",
        file_id: str = "f1",
        case_id: str = "case1",
        content: str = "Test content",
        heading_path: str = "test.pdf > Page 1",
        file_type: str = "pdf",
        filename: str = "test.pdf",
    ) -> CaseChunkEmbedding:
        return CaseChunkEmbedding(
            chunk_id=chunk_id,
            file_id=file_id,
            case_id=case_id,
            content=content,
            heading_path=heading_path,
            dense_vector=[0.1] * 768,
            content_hash=f"hash_{chunk_id}",
            is_active=True,
            file_type=file_type,
            original_filename=filename,
        )

    def test_create_table_on_first_upsert(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        emb = self._make_embedding()
        store.upsert_embeddings([emb])
        assert store.table is not None

    def test_upsert_and_count(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        embs = [
            self._make_embedding(chunk_id=f"c{i}", content=f"Content {i}")
            for i in range(5)
        ]
        store.upsert_embeddings(embs)
        assert store.get_chunk_count("case1") == 5

    def test_upsert_update_existing(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        emb1 = self._make_embedding(content="Original")
        store.upsert_embeddings([emb1])

        emb2 = self._make_embedding(content="Updated")
        store.upsert_embeddings([emb2])

        assert store.get_chunk_count("case1") == 1

    def test_delete_file_embeddings(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        embs = [
            self._make_embedding(chunk_id="c1", file_id="f1"),
            self._make_embedding(chunk_id="c2", file_id="f1"),
            self._make_embedding(chunk_id="c3", file_id="f2"),
        ]
        store.upsert_embeddings(embs)

        store.delete_file_embeddings("f1")
        # Only f2 chunk remains
        assert store.get_chunk_count("case1") == 1

    def test_delete_case_embeddings(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        embs = [
            self._make_embedding(chunk_id="c1", case_id="case1"),
            self._make_embedding(chunk_id="c2", case_id="case2"),
        ]
        store.upsert_embeddings(embs)

        store.delete_case_embeddings("case1")
        assert store.get_chunk_count("case1") == 0
        assert store.get_chunk_count("case2") == 1

    def test_case_isolation_in_count(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        embs = [
            self._make_embedding(chunk_id="c1", case_id="case1"),
            self._make_embedding(chunk_id="c2", case_id="case1"),
            self._make_embedding(chunk_id="c3", case_id="case2"),
        ]
        store.upsert_embeddings(embs)
        assert store.get_chunk_count("case1") == 2
        assert store.get_chunk_count("case2") == 1

    def test_vector_search(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        embs = [
            self._make_embedding(
                chunk_id="c1",
                case_id="case1",
                content="Employment discrimination case details",
            ),
            self._make_embedding(
                chunk_id="c2",
                case_id="case2",
                content="Unrelated case content",
            ),
        ]
        store.upsert_embeddings(embs)

        results = store.search_vector("case1", [0.1] * 768, top_k=10)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"

    def test_vector_search_respects_is_active(self, tmp_path):
        store = CaseVectorStore(db_path=str(tmp_path / "lance"))
        active = self._make_embedding(chunk_id="c1")
        inactive = CaseChunkEmbedding(
            chunk_id="c2",
            file_id="f1",
            case_id="case1",
            content="Inactive chunk",
            heading_path="test.pdf > Page 2",
            dense_vector=[0.1] * 768,
            content_hash="hash_c2",
            is_active=False,
            file_type="pdf",
            original_filename="test.pdf",
        )
        store.upsert_embeddings([active, inactive])

        results = store.search_vector("case1", [0.1] * 768, top_k=10)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"


# --- Processing pipeline: _chunk_and_embed ---


class TestChunkAndEmbed:
    @pytest.mark.asyncio
    async def test_chunk_and_embed_basic(self, case_storage, tmp_path):
        """Test the full chunk → embed → store pipeline."""
        from employee_help.casefile.processing import _chunk_and_embed
        from employee_help.retrieval.embedder import EmbeddingResult

        case = case_storage.create_case(Case(name="Test Case", user_id="test-user", organization_id="test-org"))
        cf = case_storage.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="report.pdf",
            file_type=FileType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_path="/tmp/test.pdf",
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        # Return enough embeddings for however many chunks are produced
        mock_embedder.embed_batch.side_effect = lambda texts, **kw: [
            EmbeddingResult(dense_vector=[0.1] * 768) for _ in texts
        ]

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        # Two pages with enough content (form-feed separated)
        # Small pages merge into 1 chunk by design; use large pages for 2+ chunks
        page = "This page has a lot of content. " * 120  # ~480 tokens per page
        text = page.strip() + "\f" + page.strip()

        count = await _chunk_and_embed(
            text=text,
            filename="report.pdf",
            file_type=FileType.PDF,
            file_id=cf.id,
            case_id=case.id,
            case_storage=case_storage,
            embedder=mock_embedder,
            case_vector_store=cvs,
        )

        assert count >= 2

        # Check SQLite chunks
        chunks = case_storage.get_case_chunks(file_id=cf.id)
        assert len(chunks) >= 2
        assert chunks[0].heading_path.startswith("report.pdf >")

        # Check LanceDB embeddings
        assert cvs.get_chunk_count(case.id) >= 2
        mock_embedder.embed_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunk_and_embed_empty_text(self, case_storage, tmp_path):
        """Empty text produces zero chunks."""
        from employee_help.casefile.processing import _chunk_and_embed

        mock_embedder = MagicMock()
        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        count = await _chunk_and_embed(
            text="",
            filename="empty.pdf",
            file_type=FileType.PDF,
            file_id="f1",
            case_id="case1",
            case_storage=case_storage,
            embedder=mock_embedder,
            case_vector_store=cvs,
        )

        assert count == 0
        mock_embedder.embed_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_chunk_and_embed_deletes_old_chunks(self, case_storage, tmp_path):
        """Re-embedding replaces old chunks."""
        from employee_help.casefile.processing import _chunk_and_embed
        from employee_help.retrieval.embedder import EmbeddingResult

        case = case_storage.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))
        cf = case_storage.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="doc.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=100,
            storage_path="/tmp/doc.txt",
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            EmbeddingResult(dense_vector=[0.1] * 768),
        ]

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        # First embedding
        await _chunk_and_embed(
            text="First version of the text with enough content to form a chunk.",
            filename="doc.txt",
            file_type=FileType.TXT,
            file_id=cf.id,
            case_id=case.id,
            case_storage=case_storage,
            embedder=mock_embedder,
            case_vector_store=cvs,
        )
        assert case_storage.get_case_chunk_count(case.id) == 1

        # Second embedding (replaces)
        await _chunk_and_embed(
            text="Updated text with different content for the replacement chunk.",
            filename="doc.txt",
            file_type=FileType.TXT,
            file_id=cf.id,
            case_id=case.id,
            case_storage=case_storage,
            embedder=mock_embedder,
            case_vector_store=cvs,
        )
        assert case_storage.get_case_chunk_count(case.id) == 1

        chunks = case_storage.get_case_chunks(file_id=cf.id)
        assert "Updated" in chunks[0].content

    @pytest.mark.asyncio
    async def test_chunk_and_embed_docx_generic_strategy(self, case_storage, tmp_path):
        """Non-PDF files use generic paragraph chunking."""
        from employee_help.casefile.processing import _chunk_and_embed
        from employee_help.retrieval.embedder import EmbeddingResult

        case = case_storage.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))
        cf = case_storage.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="memo.docx",
            file_type=FileType.DOCX,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size_bytes=500,
            storage_path="/tmp/memo.docx",
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            EmbeddingResult(dense_vector=[0.1] * 768),
        ]

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        count = await _chunk_and_embed(
            text="This is a Word document with sufficient content for a chunk.",
            filename="memo.docx",
            file_type=FileType.DOCX,
            file_id=cf.id,
            case_id=case.id,
            case_storage=case_storage,
            embedder=mock_embedder,
            case_vector_store=cvs,
        )

        assert count == 1
        chunks = case_storage.get_case_chunks(file_id=cf.id)
        assert chunks[0].heading_path == "memo.docx"


# --- process_file integration ---


class TestProcessFileEmbedding:
    """Integration tests for process_file with embedding.

    Uses file-based SQLite DB because process_file runs _chunk_and_embed
    in a thread pool executor, and in-memory SQLite connections can't be
    shared across threads.
    """

    @staticmethod
    def _make_case_storage(tmp_path):
        """Create a file-based CaseStorage for cross-thread usage."""
        from employee_help.storage.storage import Storage

        db_path = str(tmp_path / "test.db")
        # Initialize schema via Storage
        storage = Storage(db_path=db_path)
        storage.close()
        return CaseStorage(db_path=db_path)

    @pytest.mark.asyncio
    async def test_process_file_without_embedder(self, tmp_path):
        """process_file still works without embedder (backward compatible)."""
        from employee_help.casefile.processing import process_file

        cs = self._make_case_storage(tmp_path)
        case = cs.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))

        file_path = tmp_path / "hello.txt"
        file_path.write_text("Hello world from the test file content.")

        cf = cs.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="hello.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=file_path.stat().st_size,
            storage_path=str(file_path),
            upload_order=0,
        ))

        await process_file(cs, cf.id, case.id)

        updated = cs.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.READY
        assert "Hello world" in updated.extracted_text
        assert cs.get_case_chunk_count(case.id) == 0
        cs.close()

    @pytest.mark.asyncio
    async def test_process_file_with_embedder(self, tmp_path):
        """process_file chunks + embeds when embedder is provided."""
        from employee_help.casefile.processing import process_file
        from employee_help.retrieval.embedder import EmbeddingResult

        cs = self._make_case_storage(tmp_path)
        case = cs.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))

        file_path = tmp_path / "content.txt"
        file_path.write_text(
            "This is a longer text file with enough content to be chunked and embedded."
        )

        cf = cs.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="content.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=file_path.stat().st_size,
            storage_path=str(file_path),
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            EmbeddingResult(dense_vector=[0.1] * 768),
        ]

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        await process_file(cs, cf.id, case.id, mock_embedder, cvs)

        updated = cs.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.READY
        assert cs.get_case_chunk_count(case.id) >= 1
        assert cvs.get_chunk_count(case.id) >= 1
        cs.close()

    @pytest.mark.asyncio
    async def test_process_file_embedding_failure_doesnt_block(self, tmp_path):
        """Embedding failure doesn't prevent file from being marked READY."""
        from employee_help.casefile.processing import process_file

        cs = self._make_case_storage(tmp_path)
        case = cs.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))

        file_path = tmp_path / "test.txt"
        file_path.write_text("Some text content for embedding failure test scenario.")

        cf = cs.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="test.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=file_path.stat().st_size,
            storage_path=str(file_path),
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.side_effect = RuntimeError("GPU out of memory")

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        await process_file(cs, cf.id, case.id, mock_embedder, cvs)

        updated = cs.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.READY
        assert "Some text" in updated.extracted_text
        cs.close()

    @pytest.mark.asyncio
    async def test_process_file_broadcasts_chunk_count(self, tmp_path):
        """SSE broadcast includes chunk_count."""
        from employee_help.casefile.processing import (
            process_file,
            register_sse_client,
            unregister_sse_client,
        )
        from employee_help.retrieval.embedder import EmbeddingResult

        cs = self._make_case_storage(tmp_path)
        case = cs.create_case(Case(name="Test", user_id="test-user", organization_id="test-org"))

        file_path = tmp_path / "broadcast.txt"
        file_path.write_text("Content for the broadcast test scenario with chunks.")

        cf = cs.create_case_file(CaseFile(
            case_id=case.id,
            original_filename="broadcast.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=file_path.stat().st_size,
            storage_path=str(file_path),
            upload_order=0,
        ))

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            EmbeddingResult(dense_vector=[0.1] * 768),
        ]

        cvs = CaseVectorStore(db_path=str(tmp_path / "lance"))

        q = register_sse_client(case.id)

        await process_file(cs, cf.id, case.id, mock_embedder, cvs)

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        unregister_sse_client(case.id, q)

        ready_events = [e for e in events if e.get("status") == "ready"]
        assert len(ready_events) == 1
        assert "chunk_count" in ready_events[0]
        assert ready_events[0]["chunk_count"] >= 1
        cs.close()
