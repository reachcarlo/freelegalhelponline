"""File type extractors for case file ingestion (Strategy pattern)."""

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.docx import DocxExtractor
from employee_help.casefile.extractors.pdf import PDFExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry
from employee_help.casefile.extractors.text import PlainTextExtractor

__all__ = [
    "DocxExtractor",
    "ExtractionResult",
    "ExtractorRegistry",
    "FileExtractor",
    "PDFExtractor",
    "PlainTextExtractor",
]
