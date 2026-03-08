"""Background file processing for LITIGAGENT case file uploads."""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from employee_help.casefile.extractors.base import ExtractionResult
from employee_help.casefile.extractors.csv_ext import CSVExtractor
from employee_help.casefile.extractors.docx import DocxExtractor
from employee_help.casefile.extractors.email import EmailExtractor
from employee_help.casefile.extractors.image import ImageExtractor
from employee_help.casefile.extractors.pdf import PDFExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry
from employee_help.casefile.extractors.text import PlainTextExtractor
from employee_help.casefile.extractors.xlsx import ExcelExtractor
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import CaseChunk, FileType, ProcessingStatus

if TYPE_CHECKING:
    from employee_help.casefile.case_vector_store import CaseVectorStore
    from employee_help.retrieval.embedder import EmbeddingService

logger = structlog.get_logger(__name__)

# Maximum upload size: 50 MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Base directory for case file storage
CASES_DIR = Path("data/cases")

# Extension → FileType mapping
_EXT_TO_FILE_TYPE: dict[str, FileType] = {
    "pdf": FileType.PDF,
    "docx": FileType.DOCX,
    "xlsx": FileType.XLSX,
    "csv": FileType.CSV,
    "tsv": FileType.CSV,
    "eml": FileType.EML,
    "msg": FileType.MSG,
    "mbox": FileType.EML,
    "txt": FileType.TXT,
    "md": FileType.TXT,
    "rtf": FileType.TXT,
    "png": FileType.IMAGE,
    "jpg": FileType.IMAGE,
    "jpeg": FileType.IMAGE,
    "tiff": FileType.IMAGE,
    "tif": FileType.IMAGE,
    "bmp": FileType.IMAGE,
    "pptx": FileType.PPTX,
}

# SSE broadcast queues: case_id → list of connected client queues
_status_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

# Singleton registry
_registry: ExtractorRegistry | None = None


def get_file_type(extension: str) -> FileType | None:
    """Map a file extension to a FileType enum value."""
    return _EXT_TO_FILE_TYPE.get(extension.lower())


def get_supported_extensions() -> set[str]:
    """Return the set of all supported file extensions."""
    return set(_EXT_TO_FILE_TYPE.keys())


def get_registry() -> ExtractorRegistry:
    """Build (or return cached) ExtractorRegistry with all available extractors."""
    global _registry
    if _registry is None:
        _registry = ExtractorRegistry()
        _registry.register(PDFExtractor())
        _registry.register(DocxExtractor())
        _registry.register(ExcelExtractor())
        _registry.register(CSVExtractor())
        _registry.register(ImageExtractor())
        _registry.register(PlainTextExtractor())
        _registry.register(EmailExtractor())
    return _registry


def save_upload(case_id: str, file_id: str, filename: str, data: bytes) -> Path:
    """Save uploaded file bytes to disk and return the storage path."""
    case_dir = CASES_DIR / case_id / "files"
    case_dir.mkdir(parents=True, exist_ok=True)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    storage_path = case_dir / f"{file_id}_{safe_name}"
    storage_path.write_bytes(data)
    return storage_path


def content_hash(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode()).hexdigest()


async def broadcast_status(case_id: str, event: dict[str, Any]) -> None:
    """Push a status event to all SSE clients watching this case."""
    queues = _status_queues.get(case_id, [])
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop if client is slow


def register_sse_client(case_id: str) -> asyncio.Queue:
    """Register a new SSE client for a case. Returns the queue to consume."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _status_queues[case_id].append(q)
    return q


def unregister_sse_client(case_id: str, q: asyncio.Queue) -> None:
    """Remove an SSE client queue when the connection closes."""
    clients = _status_queues.get(case_id, [])
    if q in clients:
        clients.remove(q)
    if not clients:
        _status_queues.pop(case_id, None)


async def _chunk_and_embed(
    text: str,
    filename: str,
    file_type: FileType,
    file_id: str,
    case_id: str,
    case_storage: CaseStorage,
    embedder: EmbeddingService,
    case_vector_store: CaseVectorStore,
) -> int:
    """Chunk text, embed chunks, store in SQLite + LanceDB.

    SQLite operations run in the async thread (same thread as the connection).
    CPU-intensive embedding runs in a thread pool executor.
    Returns the number of chunks created.
    """
    from employee_help.casefile.case_vector_store import CaseChunkEmbedding
    from employee_help.casefile.chunker import chunk_case_file

    chunk_results = chunk_case_file(
        edited_text=text,
        filename=filename,
        file_type=file_type,
    )

    if not chunk_results:
        return 0

    # Convert ChunkResult → CaseChunk for SQLite
    case_chunks: list[CaseChunk] = []
    for cr in chunk_results:
        case_chunks.append(
            CaseChunk(
                file_id=file_id,
                case_id=case_id,
                chunk_index=cr.chunk_index,
                content=cr.content,
                heading_path=cr.heading_path,
                token_count=cr.token_count,
                content_hash=cr.content_hash,
            )
        )

    # SQLite operations (in async thread — safe for same-thread connection)
    case_storage.delete_case_chunks_for_file(file_id)
    case_storage.insert_case_chunks(case_chunks)

    # Embed all chunks (CPU-intensive — run in thread pool)
    texts = [c.content for c in case_chunks]
    loop = asyncio.get_event_loop()
    embedding_results = await loop.run_in_executor(
        None, embedder.embed_batch, texts
    )

    # Build LanceDB records
    file_type_str = file_type.value if hasattr(file_type, "value") else str(file_type)
    case_embeddings: list[CaseChunkEmbedding] = []
    for chunk, emb_result in zip(case_chunks, embedding_results):
        case_embeddings.append(
            CaseChunkEmbedding(
                chunk_id=chunk.id,
                file_id=file_id,
                case_id=case_id,
                content=chunk.content,
                heading_path=chunk.heading_path,
                dense_vector=emb_result.dense_vector,
                content_hash=chunk.content_hash,
                is_active=True,
                file_type=file_type_str,
                original_filename=filename,
            )
        )

    # Delete old embeddings, upsert new ones, rebuild FTS
    case_vector_store.delete_file_embeddings(file_id)
    case_vector_store.upsert_embeddings(case_embeddings)
    case_vector_store.rebuild_fts_index()

    return len(case_chunks)


async def process_file(
    case_storage: CaseStorage,
    file_id: str,
    case_id: str,
    embedder: EmbeddingService | None = None,
    case_vector_store: CaseVectorStore | None = None,
) -> None:
    """Background task: extract text from an uploaded file, then chunk + embed.

    1. Update status to PROCESSING
    2. Read file from disk
    3. Resolve extractor via registry
    4. Extract text
    5. Store extracted_text + edited_text (status: READY)
    6. Chunk + embed + store in LanceDB (if embedder provided)
    7. Broadcast SSE event
    """
    log = logger.bind(file_id=file_id, case_id=case_id)

    try:
        # Mark processing
        case_storage.update_case_file_status(file_id, ProcessingStatus.PROCESSING)
        await broadcast_status(case_id, {
            "file_id": file_id,
            "status": "processing",
        })

        # Load file metadata
        cf = case_storage.get_case_file(file_id)
        if cf is None:
            log.error("file_not_found")
            case_storage.update_case_file_status(
                file_id,
                ProcessingStatus.ERROR,
                error_message="File record not found in database",
            )
            await broadcast_status(case_id, {
                "file_id": file_id,
                "status": "error",
                "message": "File record not found in database",
            })
            return

        # Read bytes from disk
        storage_path = Path(cf.storage_path)
        if not storage_path.exists():
            raise FileNotFoundError(f"File not found on disk: {storage_path}")

        file_bytes = storage_path.read_bytes()

        # Resolve extractor
        registry = get_registry()
        ext = storage_path.suffix.lower().lstrip(".")
        extractor = registry.get_extractor(cf.mime_type, ext)

        if extractor is None:
            raise ValueError(
                f"No extractor available for {cf.original_filename} "
                f"(mime={cf.mime_type}, ext={ext})"
            )

        # Run extraction (CPU-bound — run in thread pool)
        result: ExtractionResult = await asyncio.get_event_loop().run_in_executor(
            None, extractor.extract, file_bytes, cf.original_filename
        )

        # Store results
        text = result.text.strip()
        h = content_hash(text) if text else None

        case_storage.update_case_file_text(
            file_id,
            extracted_text=text,
            edited_text=text,
            ocr_confidence=result.ocr_confidence,
            page_count=result.page_count,
            content_hash=h,
            metadata=result.metadata,
        )
        case_storage.update_case_file_status(file_id, ProcessingStatus.READY)

        log.info(
            "file_processed",
            filename=cf.original_filename,
            text_len=len(text),
            page_count=result.page_count,
            ocr_confidence=result.ocr_confidence,
            warnings=result.warnings,
        )

        # Chunk + embed (if embedding services are available)
        chunk_count = 0
        if text and embedder is not None and case_vector_store is not None:
            try:
                chunk_count = await _chunk_and_embed(
                    text,
                    cf.original_filename,
                    cf.file_type,
                    file_id,
                    case_id,
                    case_storage,
                    embedder,
                    case_vector_store,
                )
                log.info(
                    "file_embedded",
                    filename=cf.original_filename,
                    chunk_count=chunk_count,
                )
            except Exception as emb_exc:
                # Embedding failure doesn't block file readiness
                log.error(
                    "file_embedding_failed",
                    error=str(emb_exc),
                    exc_info=True,
                )

        await broadcast_status(case_id, {
            "file_id": file_id,
            "status": "ready",
            "ocr_confidence": result.ocr_confidence,
            "page_count": result.page_count,
            "chunk_count": chunk_count,
        })

    except Exception as exc:
        log.error("file_processing_failed", error=str(exc), exc_info=True)

        case_storage.update_case_file_status(
            file_id,
            ProcessingStatus.ERROR,
            error_message=str(exc),
        )

        await broadcast_status(case_id, {
            "file_id": file_id,
            "status": "error",
            "message": str(exc),
        })
