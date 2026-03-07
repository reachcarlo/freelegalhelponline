"""File type extractors for case file ingestion (Strategy pattern)."""

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry

__all__ = ["ExtractionResult", "ExtractorRegistry", "FileExtractor"]
