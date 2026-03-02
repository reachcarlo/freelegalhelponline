"""Citation verification and confidence scoring for attorney-mode LLM output.

Three layers:
- CaseCitationVerifier: queries CourtListener API for case citations
- StatuteCitationVerifier: queries local SQLite DB for statute citations
- Confidence scoring: aggregates verification into Verified/Unverified/Suspicious

Usage:
    case_verifier = CaseCitationVerifier(api_token="your-token")
    statute_verifier = StatuteCitationVerifier(storage)
    scored = score_all_citations(answer_text, case_verifier, statute_verifier)
    for s in scored:
        print(f"{s.citation_text}: {s.confidence.value}")
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import structlog

from employee_help.processing.citation_extractor import (
    ExtractedCitation,
    extract_case_citations,
    extract_statute_citations,
)
from employee_help.scraper.extractors.courtlistener import (
    AuthenticationError,
    CourtListenerClient,
    CourtListenerError,
)

if TYPE_CHECKING:
    from employee_help.storage.storage import Storage

logger = structlog.get_logger(__name__)

# California reporters — used to verify jurisdiction of lookup results.
# Mirrors _CA_REPORTERS in citation_extractor.py.
_CA_REPORTERS = frozenset(
    {
        "Cal.",
        "Cal. 2d",
        "Cal. 3d",
        "Cal. 4th",
        "Cal. 5th",
        "Cal. App.",
        "Cal. App. 2d",
        "Cal. App. 3d",
        "Cal. App. 4th",
        "Cal. App. 5th",
        "Cal. App. Supp.",
        "Cal. App. Supp. 2d",
        "Cal. App. Supp. 3d",
        "Cal. App. Supp. 4th",
        "Cal. App. Supp. 5th",
        "Cal. Rptr.",
        "Cal. Rptr. 2d",
        "Cal. Rptr. 3d",
        "Cal. Comp. Cases",
        "Cal. Unrep.",
    }
)


class VerificationStatus(str, Enum):
    """Outcome of verifying a single case citation."""

    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    WRONG_JURISDICTION = "wrong_jurisdiction"
    DATE_MISMATCH = "date_mismatch"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


@dataclass
class CaseVerificationResult:
    """Result of verifying one case citation against CourtListener."""

    citation_text: str
    status: VerificationStatus
    reporter: str | None = None
    volume: str | None = None
    page: str | None = None
    year_cited: str | None = None
    year_filed: str | None = None
    case_name: str | None = None
    cluster_id: int | None = None
    court_listener_url: str | None = None
    error_detail: str | None = None


class CaseCitationVerifier:
    """Verifies case citations in text against the CourtListener API.

    Extracts case citations using eyecite, then looks each one up via
    ``CourtListenerClient.lookup_citation()`` to determine whether it
    exists, is a California case, and has the correct filing year.
    """

    def __init__(
        self,
        client: CourtListenerClient | None = None,
        api_token: str | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            token = api_token or os.environ.get("COURTLISTENER_API_TOKEN")
            if token:
                self._client = CourtListenerClient(api_token=token)
            else:
                self._client = None
                logger.warning(
                    "citation_verifier_no_token",
                    msg="No CourtListener API token; case citation verification disabled",
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_citations(self, text: str) -> list[CaseVerificationResult]:
        """Extract and verify all California case citations in *text*.

        Returns one ``CaseVerificationResult`` per verifiable citation.
        Citations that are non-California, lack volume/reporter/page, or
        are statute citations are silently skipped.
        """
        if not self._client or not text:
            return []

        case_citations = extract_case_citations(text)

        results: list[CaseVerificationResult] = []
        for cite in case_citations:
            if not cite.is_california:
                continue
            if not (cite.volume and cite.reporter and cite.page):
                continue
            result = self._verify_single(cite)
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _verify_single(self, citation: ExtractedCitation) -> CaseVerificationResult:
        """Verify a single case citation against CourtListener."""
        base = CaseVerificationResult(
            citation_text=citation.text,
            status=VerificationStatus.ERROR,
            reporter=citation.reporter,
            volume=citation.volume,
            page=citation.page,
            year_cited=citation.year,
        )

        try:
            lookup_results = self._client.lookup_citation(
                reporter=citation.reporter,
                volume=citation.volume,
                page=citation.page,
            )
        except (CourtListenerError, Exception) as exc:
            base.error_detail = str(exc)
            logger.warning(
                "citation_verification_error",
                citation=citation.text,
                error=str(exc),
            )
            return base

        if not lookup_results:
            base.status = VerificationStatus.NOT_FOUND
            return base

        result = lookup_results[0]
        status_code = result.get("status")

        if status_code == 404:
            base.status = VerificationStatus.NOT_FOUND
            return base

        if status_code == 300:
            base.status = VerificationStatus.AMBIGUOUS
            return base

        # status == 200: found — inspect the cluster
        clusters = result.get("clusters", [])
        if not clusters:
            base.status = VerificationStatus.NOT_FOUND
            return base

        cluster = clusters[0]
        base.case_name = cluster.get("case_name")
        base.cluster_id = cluster.get("id")
        base.court_listener_url = cluster.get("absolute_url")

        date_filed = cluster.get("date_filed", "")
        if date_filed:
            base.year_filed = date_filed[:4]

        # Jurisdiction check: verify the matched reporter is Californian
        matched_citation = result.get("citation", "")
        if not self._is_california_citation(matched_citation):
            base.status = VerificationStatus.WRONG_JURISDICTION
            return base

        # Year check: only flag mismatch when both years are present
        if base.year_cited and base.year_filed:
            if base.year_cited != base.year_filed:
                base.status = VerificationStatus.DATE_MISMATCH
                return base

        base.status = VerificationStatus.VERIFIED
        return base

    @staticmethod
    def _is_california_citation(citation_text: str) -> bool:
        """Check if the matched citation string contains a California reporter."""
        for reporter in _CA_REPORTERS:
            if reporter in citation_text:
                return True
        return False


# ══════════════════════════════════════════════════════════════
# Statute citation verification (local DB)
# ══════════════════════════════════════════════════════════════

# Pattern to extract code type abbreviation from citation reporter field.
# Maps eyecite reporter strings → short code type used in LIKE matching.
_CODE_TYPE_PATTERN = re.compile(
    r"(Lab|Gov|Bus|Civ|Unemp|Health|Pen|Fam|Educ|Fin|Ins)",
    re.IGNORECASE,
)


class StatuteVerificationStatus(str, Enum):
    """Outcome of verifying a single statute citation."""

    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    REPEALED = "repealed"
    AMENDED = "amended"
    ERROR = "error"


@dataclass
class StatuteVerificationResult:
    """Result of verifying one statute citation against the knowledge base."""

    citation_text: str
    status: StatuteVerificationStatus
    section: str | None = None
    code_type: str | None = None
    matched_citation: str | None = None
    chunk_id: int | None = None
    is_active: bool | None = None
    last_ingested: str | None = None
    error_detail: str | None = None


class StatuteCitationVerifier:
    """Verifies statute citations against the local knowledge base.

    Extracts statute citations using eyecite, then looks each one up
    in the SQLite chunks table to check whether the section exists,
    is still active (not repealed), and when it was last ingested.
    """

    def __init__(
        self,
        storage: Storage,
        *,
        amended_threshold_days: int = 30,
    ) -> None:
        self._storage = storage
        self._amended_threshold_days = amended_threshold_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_citations(self, text: str) -> list[StatuteVerificationResult]:
        """Extract and verify all statute citations in *text*.

        Returns one ``StatuteVerificationResult`` per verifiable citation.
        Non-California statute citations are silently skipped.
        """
        if not text:
            return []

        statute_citations = extract_statute_citations(text)

        results: list[StatuteVerificationResult] = []
        seen: set[str] = set()
        for cite in statute_citations:
            if not cite.is_california:
                continue
            if not cite.section:
                continue
            # Deduplicate by section + reporter
            key = f"{cite.reporter}:{cite.section}"
            if key in seen:
                continue
            seen.add(key)

            result = self._verify_single(cite)
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _verify_single(
        self, citation: ExtractedCitation
    ) -> StatuteVerificationResult:
        """Verify a single statute citation against the knowledge base."""
        # Extract code type from the full citation text (reporter field
        # from eyecite is often just "Cal. Code", not the specific code).
        code_type = self._extract_code_type(citation.text)

        base = StatuteVerificationResult(
            citation_text=citation.text,
            status=StatuteVerificationStatus.ERROR,
            section=citation.section,
            code_type=code_type,
        )

        try:
            lookup = self._storage.lookup_statute_chunk(
                section_number=citation.section,
                code_type=code_type,
            )
        except Exception as exc:
            base.error_detail = str(exc)
            logger.warning(
                "statute_verification_error",
                citation=citation.text,
                error=str(exc),
            )
            return base

        if lookup is None:
            base.status = StatuteVerificationStatus.NOT_FOUND
            return base

        base.chunk_id = lookup["chunk_id"]
        base.matched_citation = lookup["citation"]
        base.is_active = lookup["is_active"]
        base.last_ingested = lookup["retrieved_at"]

        # Repealed check
        if not lookup["is_active"]:
            base.status = StatuteVerificationStatus.REPEALED
            return base

        # Amendment staleness check
        if self._is_stale(lookup["retrieved_at"]):
            base.status = StatuteVerificationStatus.AMENDED
            return base

        base.status = StatuteVerificationStatus.VERIFIED
        return base

    def _is_stale(self, retrieved_at: str | None) -> bool:
        """Check if the ingestion date is older than the threshold."""
        if not retrieved_at:
            return False
        try:
            ingested = datetime.fromisoformat(retrieved_at)
            if ingested.tzinfo is None:
                ingested = ingested.replace(tzinfo=timezone.utc)
            age = datetime.now(tz=timezone.utc) - ingested
            return age.days > self._amended_threshold_days
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _extract_code_type(reporter: str | None) -> str | None:
        """Extract the short code type from a reporter string.

        E.g. ``"Cal. Lab. Code"`` → ``"Lab"``.
        """
        if not reporter:
            return None
        m = _CODE_TYPE_PATTERN.search(reporter)
        return m.group(1) if m else None


# ══════════════════════════════════════════════════════════════
# Confidence scoring
# ══════════════════════════════════════════════════════════════

class CitationConfidence(str, Enum):
    """Aggregated confidence level for a citation."""

    VERIFIED = "verified"        # All checks pass (green)
    UNVERIFIED = "unverified"    # Not found or lookup error (yellow)
    SUSPICIOUS = "suspicious"    # Active problem detected (red)


# Mapping from individual verification statuses to confidence tiers.
_CASE_CONFIDENCE: dict[VerificationStatus, CitationConfidence] = {
    VerificationStatus.VERIFIED: CitationConfidence.VERIFIED,
    VerificationStatus.NOT_FOUND: CitationConfidence.UNVERIFIED,
    VerificationStatus.AMBIGUOUS: CitationConfidence.UNVERIFIED,
    VerificationStatus.ERROR: CitationConfidence.UNVERIFIED,
    VerificationStatus.WRONG_JURISDICTION: CitationConfidence.SUSPICIOUS,
    VerificationStatus.DATE_MISMATCH: CitationConfidence.SUSPICIOUS,
}

_STATUTE_CONFIDENCE: dict[StatuteVerificationStatus, CitationConfidence] = {
    StatuteVerificationStatus.VERIFIED: CitationConfidence.VERIFIED,
    StatuteVerificationStatus.NOT_FOUND: CitationConfidence.UNVERIFIED,
    StatuteVerificationStatus.ERROR: CitationConfidence.UNVERIFIED,
    StatuteVerificationStatus.REPEALED: CitationConfidence.SUSPICIOUS,
    StatuteVerificationStatus.AMENDED: CitationConfidence.SUSPICIOUS,
}


@dataclass
class ScoredCitation:
    """A citation with its aggregated confidence level."""

    citation_text: str
    citation_type: str               # "case" or "statute"
    confidence: CitationConfidence
    verification_status: str         # Original status value from verifier
    detail: str | None = None        # Human-readable explanation


def score_case_result(result: CaseVerificationResult) -> ScoredCitation:
    """Map a case verification result to a confidence score."""
    confidence = _CASE_CONFIDENCE.get(
        result.status, CitationConfidence.UNVERIFIED
    )
    detail = _case_detail(result)
    return ScoredCitation(
        citation_text=result.citation_text,
        citation_type="case",
        confidence=confidence,
        verification_status=result.status.value,
        detail=detail,
    )


def score_statute_result(result: StatuteVerificationResult) -> ScoredCitation:
    """Map a statute verification result to a confidence score."""
    confidence = _STATUTE_CONFIDENCE.get(
        result.status, CitationConfidence.UNVERIFIED
    )
    detail = _statute_detail(result)
    return ScoredCitation(
        citation_text=result.citation_text,
        citation_type="statute",
        confidence=confidence,
        verification_status=result.status.value,
        detail=detail,
    )


def score_all_citations(
    text: str,
    case_verifier: CaseCitationVerifier | None = None,
    statute_verifier: StatuteCitationVerifier | None = None,
) -> list[ScoredCitation]:
    """Verify and score all citations in *text*.

    Runs both case and statute verifiers (if provided) and returns
    a unified list of scored citations.
    """
    scored: list[ScoredCitation] = []

    if case_verifier:
        for result in case_verifier.verify_citations(text):
            scored.append(score_case_result(result))

    if statute_verifier:
        for result in statute_verifier.verify_citations(text):
            scored.append(score_statute_result(result))

    return scored


# ── Detail message helpers ────────────────────────────────────


def _case_detail(result: CaseVerificationResult) -> str:
    """Build a human-readable detail string for a case verification."""
    if result.status == VerificationStatus.VERIFIED:
        parts = ["Verified against CourtListener"]
        if result.case_name:
            parts.append(f"({result.case_name})")
        return " ".join(parts)
    if result.status == VerificationStatus.NOT_FOUND:
        return "Case not found in CourtListener database"
    if result.status == VerificationStatus.WRONG_JURISDICTION:
        return "Case found but is not a California case"
    if result.status == VerificationStatus.DATE_MISMATCH:
        return (
            f"Year mismatch: cited {result.year_cited}, "
            f"filed {result.year_filed}"
        )
    if result.status == VerificationStatus.AMBIGUOUS:
        return "Multiple matching cases found"
    if result.status == VerificationStatus.ERROR:
        return f"Verification error: {result.error_detail or 'unknown'}"
    return "Unknown status"


def _statute_detail(result: StatuteVerificationResult) -> str:
    """Build a human-readable detail string for a statute verification."""
    if result.status == StatuteVerificationStatus.VERIFIED:
        return f"Verified in knowledge base ({result.matched_citation or result.citation_text})"
    if result.status == StatuteVerificationStatus.NOT_FOUND:
        return "Section not found in knowledge base"
    if result.status == StatuteVerificationStatus.REPEALED:
        return "Section has been repealed"
    if result.status == StatuteVerificationStatus.AMENDED:
        return f"Section may have been amended (last ingested: {result.last_ingested or 'unknown'})"
    if result.status == StatuteVerificationStatus.ERROR:
        return f"Verification error: {result.error_detail or 'unknown'}"
    return "Unknown status"
