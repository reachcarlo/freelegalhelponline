"""Citation extraction using eyecite.

Wraps the eyecite library to extract case and statutory citations from
legal text. Provides California-jurisdiction filtering and short-form
citation resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

try:
    from eyecite import clean_text, get_citations, resolve_citations
    from eyecite.models import (
        FullCaseCitation,
        FullLawCitation,
        IdCitation,
        ShortCaseCitation,
        SupraCitation,
    )
except ImportError:
    _EYECITE_AVAILABLE = False
else:
    _EYECITE_AVAILABLE = True

logger = structlog.get_logger(__name__)

# California case reporters — all editions of state court reporters
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

# California statutory code subjects in eyecite's Cal. Code pattern
_CA_CODE_SUBJECTS = frozenset(
    {
        "Lab.",
        "Gov.",
        "Bus. & Prof.",
        "Civ. Proc.",
        "Unemp. Ins.",
        "Health & Safety",
        "Civ.",
        "Pen.",
        "Fam.",
        "Educ.",
        "Fin.",
        "Ins.",
        "Prob.",
        "Rev. & Tax.",
        "Veh.",
        "Wat.",
        "Welf. & Inst.",
    }
)


@dataclass
class ExtractedCitation:
    """A citation extracted from legal text."""

    text: str
    citation_type: str  # "case" | "statute" | "short_case" | "id" | "supra"
    volume: str | None
    reporter: str | None
    page: str | None
    pin_cite: str | None
    year: str | None
    court: str | None
    plaintiff: str | None
    defendant: str | None
    section: str | None
    span: tuple[int, int]
    is_california: bool


def _is_california_reporter(reporter: str | None) -> bool:
    """Check if a reporter abbreviation is a California reporter."""
    if not reporter:
        return False
    return reporter in _CA_REPORTERS


def _is_california_court(court: str | None) -> bool:
    """Check if a court code indicates a California court."""
    if not court:
        return False
    court_lower = court.lower()
    return court_lower.startswith("cal") or court_lower.startswith("ca.")


def _is_california_statute(cite: FullLawCitation) -> bool:
    """Check if a law citation is a California statute."""
    reporter = cite.corrected_reporter() if cite.edition_guess else None
    if reporter and reporter.startswith("Cal."):
        return True
    groups_reporter = cite.groups.get("reporter", "")
    if groups_reporter and "Cal." in groups_reporter:
        return True
    return False


def _convert_case_citation(cite: FullCaseCitation) -> ExtractedCitation:
    """Convert an eyecite FullCaseCitation to ExtractedCitation."""
    reporter = cite.corrected_reporter() if cite.edition_guess else cite.groups.get("reporter")
    court = getattr(cite.metadata, "court", None)

    is_ca = _is_california_reporter(reporter) or _is_california_court(court)

    return ExtractedCitation(
        text=cite.matched_text(),
        citation_type="case",
        volume=cite.groups.get("volume"),
        reporter=reporter,
        page=cite.groups.get("page"),
        pin_cite=cite.metadata.pin_cite,
        year=str(cite.year) if cite.year else None,
        court=court,
        plaintiff=getattr(cite.metadata, "plaintiff", None),
        defendant=getattr(cite.metadata, "defendant", None),
        section=None,
        span=cite.span(),
        is_california=is_ca,
    )


def _convert_short_case_citation(cite: ShortCaseCitation) -> ExtractedCitation:
    """Convert an eyecite ShortCaseCitation to ExtractedCitation."""
    reporter = cite.corrected_reporter() if cite.edition_guess else cite.groups.get("reporter")

    return ExtractedCitation(
        text=cite.matched_text(),
        citation_type="short_case",
        volume=cite.groups.get("volume"),
        reporter=reporter,
        page=cite.groups.get("page"),
        pin_cite=cite.metadata.pin_cite,
        year=None,
        court=getattr(cite.metadata, "court", None),
        plaintiff=None,
        defendant=None,
        section=None,
        span=cite.span(),
        is_california=_is_california_reporter(reporter),
    )


def _convert_supra_citation(cite: SupraCitation) -> ExtractedCitation:
    """Convert an eyecite SupraCitation to ExtractedCitation."""
    return ExtractedCitation(
        text=cite.matched_text(),
        citation_type="supra",
        volume=getattr(cite.metadata, "volume", None),
        reporter=None,
        page=None,
        pin_cite=cite.metadata.pin_cite,
        year=None,
        court=None,
        plaintiff=getattr(cite.metadata, "antecedent_guess", None),
        defendant=None,
        section=None,
        span=cite.span(),
        is_california=False,  # resolved later via grouping
    )


def _convert_id_citation(cite: IdCitation) -> ExtractedCitation:
    """Convert an eyecite IdCitation to ExtractedCitation."""
    return ExtractedCitation(
        text=cite.matched_text(),
        citation_type="id",
        volume=None,
        reporter=None,
        page=None,
        pin_cite=cite.metadata.pin_cite,
        year=None,
        court=None,
        plaintiff=None,
        defendant=None,
        section=None,
        span=cite.span(),
        is_california=False,  # resolved later via grouping
    )


def _convert_law_citation(cite: FullLawCitation) -> ExtractedCitation:
    """Convert an eyecite FullLawCitation to ExtractedCitation."""
    reporter = cite.corrected_reporter() if cite.edition_guess else cite.groups.get("reporter")

    return ExtractedCitation(
        text=cite.matched_text(),
        citation_type="statute",
        volume=None,
        reporter=reporter,
        page=None,
        pin_cite=cite.metadata.pin_cite,
        year=None,
        court=None,
        plaintiff=None,
        defendant=None,
        section=cite.groups.get("section"),
        span=cite.span(),
        is_california=_is_california_statute(cite),
    )


def _convert_citation(cite) -> ExtractedCitation | None:
    """Convert any eyecite citation to ExtractedCitation."""
    if isinstance(cite, FullCaseCitation):
        return _convert_case_citation(cite)
    if isinstance(cite, ShortCaseCitation):
        return _convert_short_case_citation(cite)
    if isinstance(cite, SupraCitation):
        return _convert_supra_citation(cite)
    if isinstance(cite, IdCitation):
        return _convert_id_citation(cite)
    if isinstance(cite, FullLawCitation):
        return _convert_law_citation(cite)
    return None


def extract_citations(
    text: str, *, remove_ambiguous: bool = True
) -> list[ExtractedCitation]:
    """Extract all citations from text.

    Args:
        text: Legal text to extract citations from.
        remove_ambiguous: Drop citations that match multiple reporters
            and cannot be disambiguated. Defaults to True.

    Returns:
        List of extracted citations ordered by position in text.
    """
    if not _EYECITE_AVAILABLE:
        raise ImportError(
            "eyecite is required for citation extraction. "
            "Install with: uv sync --extra rag"
        )

    if not text or not text.strip():
        return []

    cleaned = clean_text(text, ["all_whitespace"])
    raw_cites = get_citations(cleaned, remove_ambiguous=remove_ambiguous)

    results: list[ExtractedCitation] = []
    for cite in raw_cites:
        converted = _convert_citation(cite)
        if converted is not None:
            results.append(converted)

    logger.debug(
        "citations_extracted",
        total=len(results),
        cases=sum(1 for c in results if c.citation_type == "case"),
        statutes=sum(1 for c in results if c.citation_type == "statute"),
    )

    return results


def extract_case_citations(text: str) -> list[ExtractedCitation]:
    """Extract only case citations (full, short, id, supra) from text.

    Args:
        text: Legal text to extract citations from.

    Returns:
        List of case-related citations.
    """
    all_cites = extract_citations(text)
    return [c for c in all_cites if c.citation_type in {"case", "short_case", "id", "supra"}]


def extract_statute_citations(text: str) -> list[ExtractedCitation]:
    """Extract only statutory citations from text.

    Args:
        text: Legal text to extract citations from.

    Returns:
        List of statutory citations.
    """
    all_cites = extract_citations(text)
    return [c for c in all_cites if c.citation_type == "statute"]


def extract_california_citations(text: str) -> list[ExtractedCitation]:
    """Extract only California-jurisdiction citations from text.

    Includes California case citations (by reporter or court) and
    California statutory citations.

    Args:
        text: Legal text to extract citations from.

    Returns:
        List of California-specific citations.
    """
    all_cites = extract_citations(text)
    return [c for c in all_cites if c.is_california]


def resolve_short_citations(
    citations: list[ExtractedCitation], text: str
) -> dict[str, list[ExtractedCitation]]:
    """Resolve short-form citations to their antecedent full citations.

    Uses eyecite's resolution engine to group supra, id, and short-case
    citations with the full citations they refer to.

    Args:
        citations: Previously extracted citations (ignored — text is re-parsed).
        text: The original text (needed for eyecite's resolver).

    Returns:
        Dict mapping the full citation text to a list of all citations
        (including short forms) that reference the same resource.
    """
    if not _EYECITE_AVAILABLE:
        raise ImportError(
            "eyecite is required for citation extraction. "
            "Install with: uv sync --extra rag"
        )

    if not text or not text.strip():
        return {}

    cleaned = clean_text(text, ["all_whitespace"])
    raw_cites = get_citations(cleaned, remove_ambiguous=True)

    if not raw_cites:
        return {}

    resolutions = resolve_citations(raw_cites)

    grouped: dict[str, list[ExtractedCitation]] = {}
    for resource, cite_list in resolutions.items():
        # Use the full citation's text as the group key
        full_text = resource.citation.matched_text()
        group: list[ExtractedCitation] = []
        for cite in cite_list:
            converted = _convert_citation(cite)
            if converted is not None:
                # Propagate California status from the full citation
                if isinstance(resource.citation, FullCaseCitation):
                    full_converted = _convert_case_citation(resource.citation)
                    if full_converted.is_california:
                        converted.is_california = True
                group.append(converted)
        if group:
            grouped[full_text] = group

    logger.debug(
        "short_citations_resolved",
        groups=len(grouped),
        total_citations=sum(len(v) for v in grouped.values()),
    )

    return grouped
