"""Entity detection via regex patterns, spaCy NER, and legal citation whitelist.

EntityRecognizer scans text for structured PII (SSN, phone, email, case
numbers) using high-precision regex patterns and detects PERSON/ORG entities
via spaCy NER.  Legal citations are detected first and excluded from entity
results so they are never obfuscated.

spaCy is optional.  If spaCy or the ``en_core_web_sm`` model is not installed,
the recognizer degrades gracefully to regex-only detection.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Optional spaCy import (graceful degradation)
# ------------------------------------------------------------------

try:
    import spacy
except ImportError:
    spacy = None  # type: ignore[assignment]

_SPACY_AVAILABLE: bool = spacy is not None

# spaCy NER label → our entity type
_NER_LABEL_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "ORG": "COMPANY",
}


# ------------------------------------------------------------------
# Compiled patterns
# ------------------------------------------------------------------

# SSN: 3-2-4 digit groups separated by hyphens
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# EIN (Federal Employer Identification Number): 2-7 digit groups
EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")

# Phone: optional +1/1 prefix, area code with optional parens, 3-4 digits.
# Use (?<!\w) instead of \b so the match can start at an opening paren.
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Email: standard RFC-ish pattern
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Case numbers: 2-5 uppercase letters, optional separator, 2-4 digits,
# optional separator, 4+ digits  (e.g. BC-2025-12345, LASC 2024 00001)
CASE_NO_PATTERN = re.compile(r"\b[A-Z]{2,5}[-\s]?\d{2,4}[-\s]?\d{4,}\b")


# ------------------------------------------------------------------
# Legal citation whitelist — matches are EXCLUDED from entity results
# ------------------------------------------------------------------

_CITATION_PARTS = [
    # California codes: Cal. Lab. Code § 1102.5, Gov. Code § 12940, etc.
    r"Cal\.\s*(?:Lab|Gov|Bus|Civ|Evid|Fam|Prob|Pen|Veh|Ins|Corp|Fin|Wat|Welf)"
    r"\.\s*(?:&\s*Prof\.\s*)?Code\s*§§?\s*[\d.]+(?:\s*[-–]\s*[\d.]+)?",
    # Code of Civil Procedure: CCP § 2030.010
    r"(?:CCP|C\.C\.P\.)\s*§§?\s*[\d.]+",
    # CACI jury instructions: CACI No. 2505
    r"CACI\s*No\.\s*\d+[A-Z]?",
    # Federal regulations: 29 C.F.R. § 1630.2
    r"\d+\s*C\.F\.R\.\s*§§?\s*[\d.]+",
    # California case reporters: 45 Cal.App.5th 100, 12 Cal.4th 200
    r"\d+\s*Cal\.\s*(?:App\.\s*)?\d+(?:th|d|st|nd)?\s+\d+",
    # Federal reporters: 550 U.S. 398, 123 F.3d 456
    r"\d+\s*(?:U\.S\.|F\.\d+[a-z]*|F\.Supp\.\d*[a-z]*)\s+\d+",
    # United States Code: 42 U.S.C. § 2000e
    r"\d+\s*U\.S\.C\.\s*§§?\s*[\d\w.-]+",
    # California Constitution: Cal. Const., art. I, § 1
    r"Cal\.\s*Const\.\s*,?\s*art\.\s*[IVX]+\s*,?\s*§§?\s*\d+",
]

CITATION_PATTERN = re.compile("|".join(_CITATION_PARTS))


# ------------------------------------------------------------------
# Result container
# ------------------------------------------------------------------


@dataclass(frozen=True)
class RecognizedEntity:
    """A single entity detected in text."""

    entity_type: str  # e.g. "SSN", "EMAIL", "PHONE", "CASE"
    value: str
    start: int
    end: int


# ------------------------------------------------------------------
# Recognizer
# ------------------------------------------------------------------


@dataclass
class EntityRecognizer:
    """Detects structured PII entities in text using regex patterns and NER.

    Legal citations are detected first and any entity match that overlaps
    a citation span is excluded from the results.

    spaCy NER detects PERSON and ORG entities when available.  If spaCy
    or the ``en_core_web_sm`` model is not installed, NER is silently
    disabled (graceful degradation to regex-only).
    """

    _regex_patterns: list[tuple[str, re.Pattern[str]]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        # Order matters: SSN/EIN before PHONE to avoid SSN-inside-phone.
        # Each tuple is (entity_type, compiled_pattern).
        self._regex_patterns = [
            ("SSN", SSN_PATTERN),
            ("SSN", EIN_PATTERN),
            ("EMAIL", EMAIL_PATTERN),
            ("PHONE", PHONE_PATTERN),
            ("CASE", CASE_NO_PATTERN),
        ]
        # Lazy-loaded spaCy NLP pipeline (set by _ensure_ner_loaded)
        self._nlp: Any = None
        self._ner_loaded: bool = False

    def scan(self, text: str) -> list[RecognizedEntity]:
        """Return entities found in *text*.

        Legal citations are excluded so they are never obfuscated.
        Duplicate values (same type + value) are deduplicated; only the
        first occurrence is returned.
        """
        if not text:
            return []

        # Step 1: find citation spans (protected regions)
        citation_spans = self._citation_spans(text)

        # Step 2: regex scan (SSN, EIN, email, phone, case number)
        entities = self._scan_regex(text, citation_spans)

        # Step 3: NER scan (PERSON, ORG via spaCy — empty if unavailable)
        entities.extend(self._scan_ner(text, citation_spans))

        # Deduplicate by (entity_type, value), keeping first occurrence
        seen: set[tuple[str, str]] = set()
        deduped: list[RecognizedEntity] = []
        for ent in entities:
            key = (ent.entity_type, ent.value)
            if key not in seen:
                seen.add(key)
                deduped.append(ent)

        return deduped

    # ------------------------------------------------------------------
    # Internal: regex scan
    # ------------------------------------------------------------------

    def _scan_regex(
        self,
        text: str,
        citation_spans: list[tuple[int, int]],
    ) -> list[RecognizedEntity]:
        """Detect structured PII using regex patterns."""
        results: list[RecognizedEntity] = []

        for entity_type, pattern in self._regex_patterns:
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()

                # Skip if overlapping a legal citation
                if self._overlaps_citation(start, end, citation_spans):
                    continue

                results.append(
                    RecognizedEntity(
                        entity_type=entity_type,
                        value=match.group(0),
                        start=start,
                        end=end,
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Internal: NER scan (spaCy)
    # ------------------------------------------------------------------

    def _ensure_ner_loaded(self) -> None:
        """Load spaCy ``en_core_web_sm`` model on first use.

        Sets ``_ner_loaded`` to ``True`` regardless of outcome so the
        load is only attempted once.  If spaCy or the model is missing,
        ``_nlp`` stays ``None`` and NER is silently disabled.
        """
        if self._ner_loaded:
            return
        self._ner_loaded = True
        if not _SPACY_AVAILABLE:
            _log.debug("spaCy not installed — NER disabled")
            return
        try:
            self._nlp = spacy.load("en_core_web_sm")  # type: ignore[union-attr]
            _log.debug("spaCy en_core_web_sm loaded for NER")
        except OSError:
            _log.debug("spaCy model en_core_web_sm not found — NER disabled")

    def _scan_ner(
        self,
        text: str,
        citation_spans: list[tuple[int, int]],
    ) -> list[RecognizedEntity]:
        """Detect PERSON and ORG entities using spaCy NER.

        Returns an empty list if spaCy or the model is not installed.
        """
        self._ensure_ner_loaded()
        if self._nlp is None:
            return []

        doc = self._nlp(text)
        results: list[RecognizedEntity] = []

        for ent in doc.ents:
            entity_type = _NER_LABEL_MAP.get(ent.label_)
            if entity_type is None:
                continue

            start, end = ent.start_char, ent.end_char

            # Skip if overlapping a legal citation
            if self._overlaps_citation(start, end, citation_spans):
                continue

            results.append(
                RecognizedEntity(
                    entity_type=entity_type,
                    value=ent.text,
                    start=start,
                    end=end,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Internal: citation whitelist
    # ------------------------------------------------------------------

    @staticmethod
    def _citation_spans(text: str) -> list[tuple[int, int]]:
        """Return (start, end) spans for all legal citations in *text*."""
        return [(m.start(), m.end()) for m in CITATION_PATTERN.finditer(text)]

    @staticmethod
    def _overlaps_citation(
        start: int,
        end: int,
        citation_spans: list[tuple[int, int]],
    ) -> bool:
        """Return True if [start, end) overlaps any citation span."""
        for c_start, c_end in citation_spans:
            if start < c_end and end > c_start:
                return True
        return False
