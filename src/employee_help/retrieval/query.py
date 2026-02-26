"""Query preprocessor for search queries.

Handles citation detection, legal term expansion, and query normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

# Citation patterns for California statutes
CITATION_PATTERNS = [
    # "Lab. Code § 1102.5" or "Lab. Code section 1102.5"
    r"(?:Cal\.?\s+)?(?P<code>Lab(?:or)?|Gov(?:ernment)?|Bus(?:iness)?(?:\s+(?:&|and)\s+Prof(?:essions)?)?|Civ(?:il)?(?:\s+Proc(?:edure)?)?|Unemp(?:loyment)?(?:\s+Ins(?:urance)?)?|CCP|UIC|BPC)\.?\s*(?:Code)?\s*(?:§+|[Ss]ec(?:tion)?\.?)\s*(?P<section>[\d]+(?:\.\d+)?(?:\([a-z0-9]+\))*)",
    # "section 1102.5" (no code specified)
    r"[Ss]ec(?:tion)?\.?\s+(?P<section>[\d]+(?:\.\d+)?(?:\([a-z0-9]+\))*)",
    # "§ 1102.5"
    r"§+\s*(?P<section>[\d]+(?:\.\d+)?(?:\([a-z0-9]+\))*)",
    # "FEHA" or "12940"
    r"\b(?:FEHA|feha)\b",
    r"\b12940\b",
]

# Common legal abbreviation expansions
TERM_EXPANSIONS: dict[str, list[str]] = {
    "feha": ["Fair Employment and Housing Act", "Gov. Code 12940"],
    "cfra": ["California Family Rights Act", "Gov. Code 12945.2"],
    "fmla": ["Family and Medical Leave Act"],
    "dfeh": ["CRD", "Civil Rights Department", "Department of Fair Employment and Housing"],
    "crd": ["Civil Rights Department", "CRD"],
    "dir": ["Department of Industrial Relations"],
    "edd": ["Employment Development Department"],
    "osha": ["Occupational Safety and Health", "Cal/OSHA"],
    "cal/osha": ["California Occupational Safety and Health"],
    "wc": ["workers' compensation", "workers compensation"],
    "ui": ["unemployment insurance"],
    "sdi": ["State Disability Insurance"],
    "pfl": ["Paid Family Leave"],
    "dlse": ["Division of Labor Standards Enforcement", "Labor Commissioner"],
    "warn": ["Worker Adjustment and Retraining Notification"],
    "ada": ["Americans with Disabilities Act"],
    "flsa": ["Fair Labor Standards Act"],
    "nlra": ["National Labor Relations Act"],
    "eeoc": ["Equal Employment Opportunity Commission"],
}

# Code abbreviation normalization
CODE_ABBREVIATIONS: dict[str, str] = {
    "lab": "Lab. Code",
    "labor": "Lab. Code",
    "gov": "Gov. Code",
    "government": "Gov. Code",
    "bus": "Bus. & Prof. Code",
    "business": "Bus. & Prof. Code",
    "bpc": "Bus. & Prof. Code",
    "civ": "CCP",
    "civil": "CCP",
    "ccp": "CCP",
    "unemp": "Unemp. Ins. Code",
    "unemployment": "Unemp. Ins. Code",
    "uic": "Unemp. Ins. Code",
}


@dataclass
class ProcessedQuery:
    """Preprocessed query with metadata."""

    original_query: str
    normalized_query: str
    has_citation: bool = False
    cited_section: str | None = None
    cited_code: str | None = None
    expanded_terms: list[str] = field(default_factory=list)


class QueryPreprocessor:
    """Preprocesses search queries for optimal retrieval."""

    def __init__(self) -> None:
        self._citation_patterns = [re.compile(p, re.IGNORECASE) for p in CITATION_PATTERNS]
        self.logger = structlog.get_logger(__name__)

    def preprocess(self, query: str) -> ProcessedQuery:
        """Preprocess a query: detect citations, expand terms, normalize.

        Args:
            query: Raw user query string.

        Returns:
            ProcessedQuery with normalized query and metadata.
        """
        result = ProcessedQuery(
            original_query=query,
            normalized_query=query.strip(),
        )

        # Detect citations
        self._detect_citations(result)

        # Expand legal abbreviations
        self._expand_terms(result)

        # Normalize
        self._normalize(result)

        self.logger.debug(
            "query_preprocessed",
            original=result.original_query,
            has_citation=result.has_citation,
            cited_section=result.cited_section,
            expanded_terms=result.expanded_terms,
        )

        return result

    def _detect_citations(self, result: ProcessedQuery) -> None:
        """Detect citation patterns in the query."""
        for pattern in self._citation_patterns:
            match = pattern.search(result.original_query)
            if match:
                result.has_citation = True

                groups = match.groupdict()
                if "section" in groups and groups["section"]:
                    result.cited_section = groups["section"]
                if "code" in groups and groups["code"]:
                    code_key = groups["code"].lower().split()[0]
                    result.cited_code = CODE_ABBREVIATIONS.get(code_key, groups["code"])

                break

    def _expand_terms(self, result: ProcessedQuery) -> None:
        """Expand known legal abbreviations in the query."""
        words = result.original_query.lower().split()
        for word in words:
            # Strip punctuation for matching
            clean_word = re.sub(r"[^\w/]", "", word)
            if clean_word in TERM_EXPANSIONS:
                result.expanded_terms.extend(TERM_EXPANSIONS[clean_word])

    def _normalize(self, result: ProcessedQuery) -> None:
        """Normalize the query text."""
        normalized = result.original_query.strip()

        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Keep original casing for citation searches, but strip trailing punctuation
        normalized = normalized.rstrip("?.!,;:")

        result.normalized_query = normalized
