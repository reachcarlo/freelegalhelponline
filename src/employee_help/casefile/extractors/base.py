"""Base interface for file type extractors (Strategy pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    """Result of extracting text from a file."""

    text: str
    page_count: int | None = None
    ocr_confidence: float | None = None
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class FileExtractor(ABC):
    """Base interface for all file type extractors."""

    @abstractmethod
    def can_extract(self, mime_type: str, extension: str) -> bool:
        """Return True if this extractor handles the given file type."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract text content from the given file bytes."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this extractor supports."""
