"""Tests for the embedding service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.retrieval.embedder import (
    QUERY_PREFIX,
    ChunkEmbedding,
    EmbeddingResult,
    EmbeddingService,
)
from employee_help.storage.models import Chunk, ContentCategory


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""

    def test_creation(self):
        result = EmbeddingResult(dense_vector=[0.1, 0.2, 0.3])
        assert len(result.dense_vector) == 3


class TestChunkEmbedding:
    """Tests for ChunkEmbedding dataclass."""

    def test_creation(self):
        emb = ChunkEmbedding(
            chunk_id=1,
            document_id=10,
            source_id=2,
            content_category="statutory_code",
            citation="Cal. Lab. Code § 1102.5",
            content="Test content",
            heading_path="Test > Path",
            dense_vector=[0.1] * 768,
            content_hash="abc123",
            is_active=True,
            source_url="https://example.com",
            model_version="BAAI/bge-base-en-v1.5",
        )
        assert emb.chunk_id == 1
        assert emb.citation == "Cal. Lab. Code § 1102.5"
        assert len(emb.dense_vector) == 768


class TestEmbeddingService:
    """Tests for EmbeddingService with mocked model."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock SentenceTransformer model."""
        import numpy as np

        model = MagicMock()
        model.get_sentence_embedding_dimension.return_value = 768
        model.max_seq_length = 512
        model.encode.return_value = np.random.rand(3, 768).astype("float32")
        return model

    @pytest.fixture
    def service(self, mock_model):
        """Create an EmbeddingService with a mocked model."""
        svc = EmbeddingService(model_name="test-model", device="cpu")
        svc._model = mock_model
        return svc

    def test_dimension(self, service):
        assert service.dimension == 768

    def test_model_version(self, service):
        assert service.model_version == "test-model"

    def test_embed_text_no_prefix(self, service, mock_model):
        import numpy as np

        mock_model.encode.return_value = np.random.rand(1, 768).astype("float32")
        result = service.embed_text("test text")
        assert isinstance(result, EmbeddingResult)
        assert len(result.dense_vector) == 768

        # embed_text should NOT add query prefix
        call_texts = mock_model.encode.call_args[0][0]
        assert call_texts == ["test text"]

    def test_embed_query_adds_prefix(self, service, mock_model):
        import numpy as np

        mock_model.encode.return_value = np.random.rand(1, 768).astype("float32")
        result = service.embed_query("minimum wage in California")
        assert isinstance(result, EmbeddingResult)
        assert len(result.dense_vector) == 768

        # embed_query SHOULD add the BGE instruction prefix
        call_texts = mock_model.encode.call_args[0][0]
        assert call_texts == [QUERY_PREFIX + "minimum wage in California"]

    def test_embed_batch(self, service, mock_model):
        import numpy as np

        mock_model.encode.return_value = np.random.rand(3, 768).astype("float32")
        results = service.embed_batch(["text1", "text2", "text3"])
        assert len(results) == 3
        for r in results:
            assert len(r.dense_vector) == 768

    def test_embed_empty_batch(self, service, mock_model):
        results = service.embed_batch([])
        assert results == []

    def test_embed_chunks(self, service, mock_model):
        import numpy as np

        chunks = [
            Chunk(
                content="Test content 1",
                content_hash="hash1",
                chunk_index=0,
                heading_path="Test",
                token_count=10,
                document_id=1,
                id=100,
                content_category=ContentCategory.STATUTORY_CODE,
                citation="Cal. Lab. Code § 1",
                is_active=True,
            ),
            Chunk(
                content="Test content 2",
                content_hash="hash2",
                chunk_index=1,
                heading_path="Test2",
                token_count=20,
                document_id=2,
                id=101,
                content_category=ContentCategory.AGENCY_GUIDANCE,
                is_active=True,
            ),
        ]

        mock_model.encode.return_value = np.random.rand(2, 768).astype("float32")

        embeddings = service.embed_chunks(
            chunks,
            source_id=5,
            doc_url_map={1: "https://example.com/1", 2: "https://example.com/2"},
        )

        assert len(embeddings) == 2
        assert embeddings[0].chunk_id == 100
        assert embeddings[0].source_id == 5
        assert embeddings[0].citation == "Cal. Lab. Code § 1"
        assert embeddings[0].model_version == "test-model"
        assert embeddings[1].content_category == "agency_guidance"

    def test_embed_chunks_empty(self, service):
        result = service.embed_chunks([], source_id=1)
        assert result == []

    def test_embed_chunks_skips_empty_content(self, service, mock_model):
        import numpy as np

        chunks = [
            Chunk(
                content="Valid content",
                content_hash="hash1",
                chunk_index=0,
                heading_path="Test",
                token_count=10,
                document_id=1,
                id=100,
                content_category=ContentCategory.STATUTORY_CODE,
                is_active=True,
            ),
            Chunk(
                content="",
                content_hash="hash2",
                chunk_index=1,
                heading_path="Empty",
                token_count=0,
                document_id=1,
                id=101,
                content_category=ContentCategory.STATUTORY_CODE,
                is_active=True,
            ),
        ]

        mock_model.encode.return_value = np.random.rand(1, 768).astype("float32")
        embeddings = service.embed_chunks(chunks, source_id=1)
        assert len(embeddings) == 1
        assert embeddings[0].chunk_id == 100

    def test_embed_chunks_survives_batch_failure(self, service, mock_model):
        import numpy as np

        chunks = [
            Chunk(
                content=f"Content {i}",
                content_hash=f"hash{i}",
                chunk_index=i,
                heading_path="Test",
                token_count=10,
                document_id=1,
                id=i,
                content_category=ContentCategory.STATUTORY_CODE,
                is_active=True,
            )
            for i in range(5)
        ]

        call_count = 0

        def failing_encode(texts, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("OOM error")
            return np.random.rand(len(texts), 768).astype("float32")

        mock_model.encode.side_effect = failing_encode
        # batch_size=3 means 2 batches: [0,1,2] (fails) and [3,4] (succeeds)
        embeddings = service.embed_chunks(chunks, source_id=1, batch_size=3)
        assert len(embeddings) == 2  # Only second batch succeeds

    def test_import_error_without_sentence_transformers(self):
        svc = EmbeddingService(model_name="test", device="cpu")
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                svc._load_model()
