"""Background file processing for LITIGAGENT case file uploads."""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import structlog

from employee_help.casefile.extractors.base import ExtractionResult
from employee_help.casefile.extractors.docx import DocxExtractor
from employee_help.casefile.extractors.email import EmailExtractor
from employee_help.casefile.extractors.pdf import PDFExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry
from employee_help.casefile.extractors.text import PlainTextExtractor
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import FileType, ProcessingStatus

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


async def process_file(
    case_storage: CaseStorage,
    file_id: str,
    case_id: str,
) -> None:
    """Background task: extract text from an uploaded file.

    1. Update status to PROCESSING
    2. Read file from disk
    3. Resolve extractor via registry
    4. Extract text
    5. Store extracted_text + edited_text (status: READY)
    6. Broadcast SSE event
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

        await broadcast_status(case_id, {
            "file_id": file_id,
            "status": "ready",
            "ocr_confidence": result.ocr_confidence,
            "page_count": result.page_count,
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
