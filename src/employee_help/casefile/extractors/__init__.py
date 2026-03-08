"""File type extractors for case file ingestion (Strategy pattern)."""

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.csv_ext import CSVExtractor
from employee_help.casefile.extractors.docx import DocxExtractor
from employee_help.casefile.extractors.email import EmailExtractor
from employee_help.casefile.extractors.image import ImageExtractor
from employee_help.casefile.extractors.pdf import PDFExtractor
from employee_help.casefile.extractors.registry import ExtractorRegistry
from employee_help.casefile.extractors.text import PlainTextExtractor
from employee_help.casefile.extractors.xlsx import ExcelExtractor

__all__ = [
    "CSVExtractor",
    "DocxExtractor",
    "EmailExtractor",
    "ExcelExtractor",
    "ExtractionResult",
    "ImageExtractor",
    "ExtractorRegistry",
    "FileExtractor",
    "PDFExtractor",
    "PlainTextExtractor",
]
