"""Embedding service for generating dense vectors from text.

Uses BGE-base-en-v1.5 for dense embeddings. BM25/FTS handled by LanceDB.
BGE models use an asymmetric query prefix for retrieval tasks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from employee_help.storage.models import Chunk

logger = structlog.get_logger()

# BGE models use this prefix for queries in retrieval tasks.
# Documents are embedded without a prefix.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@dataclass
class EmbeddingResult:
    """Result of embedding a single text."""

    dense_vector: list[float]


@dataclass
class ChunkEmbedding:
    """Embedding with chunk metadata for storage in the vector store."""

    chunk_id: int
    document_id: int
    source_id: int
    content_category: str
    citation: str | None
    content: str
    heading_path: str
    dense_vector: list[float]
    content_hash: str
    is_active: bool
    source_url: str = ""
    model_version: str = ""
    language: str = "en"


class EmbeddingService:
    """Generates embeddings using BGE-base-en-v1.5 (or compatible sentence-transformers model).

    BGE models are asymmetric: queries get a prefix instruction while
    documents are embedded as-is. Use ``embed_query`` for search queries
    and ``embed_batch`` / ``embed_chunks`` for document content.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model = None
        self.logger = structlog.get_logger(
            __name__,
            model=model_name,
            device=device,
        )

    def _load_model(self) -> None:
        """Lazy-load the embedding model."""
        if self._model is not None:
            return

        self.logger.info("loading_embedding_model")
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
            )
            self.logger.info(
                "embedding_model_loaded",
                dim=self._model.get_sentence_embedding_dimension(),
                max_seq_length=self._model.max_seq_length,
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install with: uv pip install -e '.[rag]'"
            )

    @property
    def model(self):
        self._load_model()
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()

    @property
    def model_version(self) -> str:
        return self.model_name

    def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a search query with the BGE retrieval instruction prefix.

        BGE models are asymmetric: queries must be prefixed with an
        instruction for optimal retrieval quality.
        """
        prefixed = QUERY_PREFIX + query
        return self._encode_single(prefixed)

    def embed_text(self, text: str) -> EmbeddingResult:
        """Embed a single document text (no query prefix)."""
        return self._encode_single(text)

    def _encode_single(self, text: str) -> EmbeddingResult:
        """Encode a single text string."""
        model = self.model
        embedding = model.encode(
            [text],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return EmbeddingResult(dense_vector=embedding[0].tolist())

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[EmbeddingResult]:
        """Embed a batch of document texts (no query prefix).

        Uses a single model.encode() call for optimal throughput.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size for model inference.

        Returns:
            List of EmbeddingResult with dense vectors.
        """
        if not texts:
            return []

        model = self.model

        self.logger.debug("embedding_batch", count=len(texts), batch_size=batch_size)

        dense_embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        return [
            EmbeddingResult(dense_vector=vec.tolist())
            for vec in dense_embeddings
        ]

    def embed_chunks(
        self,
        chunks: list[Chunk],
        source_id: int,
        batch_size: int = 32,
        doc_url_map: dict[int, str] | None = None,
        doc_language_map: dict[int, str] | None = None,
    ) -> list[ChunkEmbedding]:
        """Embed chunks with metadata for vector store insertion.

        Processes chunks in batches with progress logging and ETA estimation.
        Individual chunk failures are logged and skipped rather than aborting
        the entire batch.

        Args:
            chunks: List of Chunk objects from the database.
            source_id: Source ID for all chunks.
            batch_size: Batch size for model inference.
            doc_url_map: Optional mapping of document_id -> source_url.
            doc_language_map: Optional mapping of document_id -> language code.

        Returns:
            List of ChunkEmbedding objects ready for vector store.
        """
        if not chunks:
            return []

        doc_url_map = doc_url_map or {}
        doc_language_map = doc_language_map or {}
        total = len(chunks)
        log_interval = max(batch_size, 500 - (500 % batch_size))  # nearest multiple of batch_size <= 500

        self.logger.info("embedding_chunks_start", total=total, batch_size=batch_size)

        chunk_embeddings: list[ChunkEmbedding] = []
        skipped = 0
        t_start = time.monotonic()

        for i in range(0, total, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = []
            valid_indices = []

            for j, chunk in enumerate(batch_chunks):
                if not chunk.content or not chunk.content.strip():
                    self.logger.warning(
                        "skipping_empty_chunk",
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                    )
                    skipped += 1
                    continue
                batch_texts.append(chunk.content)
                valid_indices.append(j)

            if not batch_texts:
                continue

            try:
                batch_results = self.embed_batch(batch_texts, batch_size=batch_size)
            except Exception as e:
                self.logger.error(
                    "batch_embedding_failed",
                    batch_start=i,
                    batch_size=len(batch_texts),
                    error=str(e),
                )
                skipped += len(batch_texts)
                continue

            for result_idx, chunk_idx in enumerate(valid_indices):
                chunk = batch_chunks[chunk_idx]
                chunk_embeddings.append(
                    ChunkEmbedding(
                        chunk_id=chunk.id or 0,
                        document_id=chunk.document_id or 0,
                        source_id=source_id,
                        content_category=(
                            chunk.content_category.value
                            if hasattr(chunk.content_category, "value")
                            else str(chunk.content_category)
                        ),
                        citation=chunk.citation,
                        content=chunk.content,
                        heading_path=chunk.heading_path,
                        dense_vector=batch_results[result_idx].dense_vector,
                        content_hash=chunk.content_hash,
                        is_active=chunk.is_active,
                        source_url=doc_url_map.get(chunk.document_id or 0, ""),
                        model_version=self.model_version,
                        language=doc_language_map.get(chunk.document_id or 0, "en"),
                    )
                )

            processed = min(i + batch_size, total)
            if processed % log_interval < batch_size or processed == total:
                elapsed = time.monotonic() - t_start
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                self.logger.info(
                    "embedding_progress",
                    processed=processed,
                    total=total,
                    percent=f"{processed / total * 100:.1f}%",
                    rate=f"{rate:.1f} chunks/s",
                    eta_seconds=f"{eta:.0f}",
                )

        self.logger.info(
            "embedding_chunks_complete",
            embedded=len(chunk_embeddings),
            skipped=skipped,
            total=total,
        )
        return chunk_embeddings
