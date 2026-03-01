"""Opinion loader for California employment case law.

Bulk download pipeline that paginates through CA Supreme Court and Courts
of Appeal opinions via the CourtListener API, runs Eyecite on each opinion
to extract cited statutes, and filters to opinions citing employment
statutes in our knowledge base.

Usage:
    loader = OpinionLoader(api_token="your-token")
    for opinion in loader.load(max_opinions=500):
        print(opinion.case_name, opinion.cited_statutes)

The court list and employment statute filter set are configurable for
extensibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog
from bs4 import BeautifulSoup

from employee_help.processing.citation_extractor import (
    ExtractedCitation,
    extract_citations,
)
from employee_help.scraper.extractors.courtlistener import (
    CourtListenerClient,
    CourtListenerError,
)

logger = structlog.get_logger(__name__)

# Employment-related California statute patterns.
# These are keyword patterns matched against eyecite-extracted statutory
# citations (reporter field) and also against the raw opinion text for
# non-Bluebook citation formats.
#
# Mapping: display label -> list of regex patterns to match
DEFAULT_EMPLOYMENT_STATUTES: dict[str, list[str]] = {
    "Labor Code": [
        r"Cal\.\s*Lab\.\s*Code",
        r"Labor\s+Code",
        r"Lab\.\s*Code",
    ],
    "Government Code (FEHA)": [
        r"Cal\.\s*Gov\.\s*Code",
        r"Government\s+Code",
        r"Gov\.\s*Code",
    ],
    "Unemployment Insurance Code": [
        r"Cal\.\s*Unemp\.\s*Ins\.\s*Code",
        r"Unemployment\s+Insurance\s+Code",
        r"Unemp\.\s*Ins\.\s*Code",
    ],
    "Business & Professions Code": [
        r"Cal\.\s*Bus\.\s*&\s*Prof\.\s*Code",
        r"Business\s+and\s+Professions\s+Code",
        r"Bus\.\s*&?\s*Prof\.\s*Code",
    ],
    "Code of Civil Procedure": [
        r"Cal\.\s*Civ\.\s*Proc\.\s*Code",
        r"Code\s+of\s+Civil\s+Procedure",
        r"Civ\.\s*Proc\.\s*Code",
        r"C\.C\.P\.",
    ],
}

# Key FEHA sections that strongly indicate employment relevance
_FEHA_SECTIONS = frozenset(
    {
        "12900", "12920", "12921", "12926", "12940", "12941", "12942",
        "12943", "12944", "12945", "12945.2", "12945.5", "12945.6",
        "12950", "12950.1", "12960", "12965",
    }
)

# Key Labor Code sections for employment
_LABOR_SECTIONS = frozenset(
    {
        "98", "98.6", "200", "201", "202", "203", "204", "210",
        "226", "226.7", "232", "510", "512", "1021.5",
        "1024.5", "1024.6", "1098", "1098.5", "1099",
        "1102.5", "1102.6", "2698", "2699", "2699.3",
    }
)

# Default California courts to search
DEFAULT_COURTS = ["cal", "calctapp"]

# CourtListener opinion text fields, in preference order
_TEXT_FIELDS = [
    "html_with_citations",
    "plain_text",
    "html_columbia",
    "html_lawbox",
    "html_anon_2020",
    "html",
    "xml_harvard",
]

# Employment-related search queries for CourtListener
DEFAULT_SEARCH_QUERIES = [
    '"Labor Code" "wrongful termination"',
    '"Government Code" "section 12940"',
    '"FEHA" employment discrimination',
    '"Labor Code" "section 1102.5" retaliation',
    '"Labor Code" "section 98.6"',
    '"PAGA" "Labor Code" "section 2699"',
    '"wage and hour" "Labor Code"',
    '"Fair Employment and Housing Act"',
    '"wrongful termination" "public policy"',
    '"employment discrimination" "disparate treatment"',
]


@dataclass
class LoadedOpinion:
    """An opinion loaded from CourtListener with extracted metadata."""

    cluster_id: int
    opinion_id: int | None
    case_name: str
    case_name_full: str | None
    date_filed: str | None
    court_id: str | None
    docket_number: str | None
    citations: list[str]
    precedential_status: str | None
    opinion_text: str
    opinion_type: str | None
    cited_statutes: list[ExtractedCitation]
    cited_cases: list[ExtractedCitation]
    all_citations: list[ExtractedCitation]
    matched_employment_codes: list[str]
    absolute_url: str | None


@dataclass
class LoaderStats:
    """Statistics from an opinion loading run."""

    opinions_fetched: int = 0
    opinions_accepted: int = 0
    opinions_rejected: int = 0
    opinions_errors: int = 0
    pages_fetched: int = 0
    queries_searched: int = 0
    seen_cluster_ids: set[int] = field(default_factory=set)


def _extract_plain_text(opinion_data: dict) -> str:
    """Extract plain text from an opinion's various text fields.

    CourtListener stores opinion text in multiple formats. We try each
    in preference order and strip HTML if needed.
    """
    for field_name in _TEXT_FIELDS:
        content = opinion_data.get(field_name)
        if content and isinstance(content, str) and len(content.strip()) > 50:
            if "<" in content and ">" in content:
                # Strip HTML tags
                soup = BeautifulSoup(content, "html.parser")
                return soup.get_text(separator=" ", strip=True)
            return content.strip()
    return ""


def _matches_employment_statutes(
    citations: list[ExtractedCitation],
    opinion_text: str,
    statute_patterns: dict[str, list[str]],
) -> list[str]:
    """Check if an opinion cites employment-relevant statutes.

    Two-pass approach:
    1. Check eyecite-extracted statutory citations against known patterns.
    2. Fallback: regex search on raw text for non-Bluebook citation formats
       (e.g., "Labor Code section 1102.5").

    Returns:
        List of matched employment code labels (e.g., ["Labor Code", "Government Code (FEHA)"]).
    """
    matched: set[str] = set()

    # Pass 1: Check eyecite-extracted statute citations
    for cite in citations:
        if cite.citation_type != "statute":
            continue
        reporter = cite.reporter or ""
        for label, patterns in statute_patterns.items():
            for pattern in patterns:
                if re.search(pattern, reporter, re.IGNORECASE):
                    matched.add(label)
                    break

    # Pass 2: Regex fallback on raw text for non-Bluebook formats
    # Only check codes not already matched via eyecite
    text_sample = opinion_text[:10000]  # Check first 10K chars for efficiency
    for label, patterns in statute_patterns.items():
        if label in matched:
            continue
        for pattern in patterns:
            if re.search(pattern, text_sample, re.IGNORECASE):
                matched.add(label)
                break

    return sorted(matched)


def _has_strong_employment_signal(
    citations: list[ExtractedCitation],
    opinion_text: str,
) -> bool:
    """Check for strong employment law signals beyond statute mentions.

    Detects key FEHA sections, Labor Code retaliation sections, or
    employment-specific terminology that indicates the opinion is
    substantively about employment law (not just a passing mention).
    """
    # Check for key FEHA or Labor Code sections in extracted citations
    for cite in citations:
        if cite.citation_type == "statute" and cite.section:
            section = cite.section.split("-")[0].strip()
            if section in _FEHA_SECTIONS or section in _LABOR_SECTIONS:
                return True

    # Check for employment-specific terms in the opinion text
    text_lower = opinion_text[:15000].lower()
    employment_terms = [
        "wrongful termination",
        "employment discrimination",
        "feha",
        "fair employment and housing",
        "sexual harassment",
        "hostile work environment",
        "retaliation",
        "whistleblower",
        "wage and hour",
        "unpaid wages",
        "overtime",
        "meal break",
        "rest period",
        "paga",
        "private attorneys general",
        "workers' compensation",
    ]
    term_count = sum(1 for term in employment_terms if term in text_lower)
    return term_count >= 2


class OpinionLoader:
    """Bulk download pipeline for California employment case law.

    Paginates through CourtListener search results, fetches opinion text,
    extracts citations via Eyecite, and filters to employment-relevant
    opinions.

    Args:
        api_token: CourtListener API token.
        courts: Court ID codes to search. Defaults to CA Supreme Court
            + all Courts of Appeal.
        employment_statutes: Statute pattern mapping for employment
            relevance filtering. Defaults to Labor Code, Gov Code,
            UIC, B&P, CCP.
        search_queries: List of search queries to run. Defaults to
            employment-focused queries.
        filed_after: Only include opinions filed after this date (YYYY-MM-DD).
        filed_before: Only include opinions filed before this date.
    """

    def __init__(
        self,
        api_token: str | None = None,
        *,
        courts: list[str] | None = None,
        employment_statutes: dict[str, list[str]] | None = None,
        search_queries: list[str] | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        client: CourtListenerClient | None = None,
    ):
        self._client = client or CourtListenerClient(api_token=api_token)
        self._owns_client = client is None
        self._courts = courts or DEFAULT_COURTS
        self._statutes = employment_statutes or DEFAULT_EMPLOYMENT_STATUTES
        self._queries = search_queries or DEFAULT_SEARCH_QUERIES
        self._filed_after = filed_after
        self._filed_before = filed_before
        self._stats = LoaderStats()

    @property
    def stats(self) -> LoaderStats:
        return self._stats

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpinionLoader:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def load(
        self,
        *,
        max_opinions: int | None = None,
        max_pages_per_query: int | None = None,
    ):
        """Load employment-relevant opinions from CourtListener.

        Iterates through configured search queries, paginates results,
        fetches opinion text, extracts citations, and yields opinions
        that cite employment statutes.

        Args:
            max_opinions: Stop after yielding this many opinions.
            max_pages_per_query: Maximum pages to fetch per search query.

        Yields:
            LoadedOpinion objects for employment-relevant opinions.
        """
        self._stats = LoaderStats()

        for query in self._queries:
            if max_opinions and self._stats.opinions_accepted >= max_opinions:
                break

            self._stats.queries_searched += 1
            logger.info("opinion_loader_search", query=query)

            try:
                search_result = self._client.search_opinions(
                    query,
                    courts=self._courts,
                    filed_after=self._filed_after,
                    filed_before=self._filed_before,
                    status="precedential",
                )
            except CourtListenerError as exc:
                logger.warning("search_failed", query=query, error=str(exc))
                continue

            for page in self._client.paginate(
                search_result, max_pages=max_pages_per_query
            ):
                self._stats.pages_fetched += 1

                for result in page:
                    if max_opinions and self._stats.opinions_accepted >= max_opinions:
                        return

                    cluster_id = result.get("cluster_id")
                    if not cluster_id:
                        continue

                    # Skip already-seen clusters (dedup across queries)
                    if cluster_id in self._stats.seen_cluster_ids:
                        continue
                    self._stats.seen_cluster_ids.add(cluster_id)

                    opinion = self._process_search_result(result)
                    if opinion is not None:
                        yield opinion

    def _process_search_result(self, result: dict) -> LoadedOpinion | None:
        """Process a single search result into a LoadedOpinion if relevant.

        Fetches the full opinion text from the API, extracts citations,
        and checks for employment relevance.
        """
        cluster_id = result.get("cluster_id")
        case_name = result.get("caseName", "Unknown")

        self._stats.opinions_fetched += 1

        try:
            opinion_text, opinion_id, opinion_type = self._fetch_opinion_text(
                cluster_id
            )
        except CourtListenerError as exc:
            logger.warning(
                "opinion_fetch_failed",
                cluster_id=cluster_id,
                case_name=case_name,
                error=str(exc),
            )
            self._stats.opinions_errors += 1
            return None

        if not opinion_text or len(opinion_text) < 100:
            logger.debug(
                "opinion_text_too_short",
                cluster_id=cluster_id,
                case_name=case_name,
                length=len(opinion_text),
            )
            self._stats.opinions_rejected += 1
            return None

        # Extract citations via Eyecite
        all_citations = extract_citations(opinion_text)
        statutes = [c for c in all_citations if c.citation_type == "statute"]
        cases = [c for c in all_citations if c.citation_type in {"case", "short_case"}]

        # Check employment relevance
        matched_codes = _matches_employment_statutes(
            all_citations, opinion_text, self._statutes
        )

        if not matched_codes:
            # Fallback: check for strong employment signals
            if not _has_strong_employment_signal(all_citations, opinion_text):
                logger.debug(
                    "opinion_not_employment",
                    cluster_id=cluster_id,
                    case_name=case_name,
                )
                self._stats.opinions_rejected += 1
                return None
            matched_codes = ["Employment (by keyword)"]

        self._stats.opinions_accepted += 1

        citation_strings = result.get("citation", [])
        if isinstance(citation_strings, str):
            citation_strings = [citation_strings]

        logger.info(
            "opinion_accepted",
            cluster_id=cluster_id,
            case_name=case_name,
            matched_codes=matched_codes,
            statutes_found=len(statutes),
            cases_found=len(cases),
        )

        return LoadedOpinion(
            cluster_id=cluster_id,
            opinion_id=opinion_id,
            case_name=case_name,
            case_name_full=result.get("caseNameFull"),
            date_filed=result.get("dateFiled"),
            court_id=result.get("court_id"),
            docket_number=result.get("docketNumber"),
            citations=citation_strings,
            precedential_status=result.get("status"),
            opinion_text=opinion_text,
            opinion_type=opinion_type,
            cited_statutes=statutes,
            cited_cases=cases,
            all_citations=all_citations,
            matched_employment_codes=matched_codes,
            absolute_url=result.get("absolute_url"),
        )

    def _fetch_opinion_text(
        self, cluster_id: int
    ) -> tuple[str, int | None, str | None]:
        """Fetch opinion text for a cluster.

        Fetches the cluster to find sub-opinions, then fetches the lead
        opinion's text.

        Returns:
            Tuple of (opinion_text, opinion_id, opinion_type).
        """
        cluster = self._client.fetch_cluster(
            cluster_id,
            fields=["id", "sub_opinions"],
        )

        sub_opinions = cluster.get("sub_opinions", [])
        if not sub_opinions:
            return "", None, None

        # Extract opinion ID from the first sub-opinion URL
        opinion_url = sub_opinions[0]
        opinion_id = _extract_id_from_url(opinion_url)
        if opinion_id is None:
            return "", None, None

        opinion_data = self._client.fetch_opinion(
            opinion_id,
            fields=["id", "type"] + _TEXT_FIELDS,
        )

        text = _extract_plain_text(opinion_data)
        opinion_type = opinion_data.get("type")

        return text, opinion_id, opinion_type


def _extract_id_from_url(url: str) -> int | None:
    """Extract numeric ID from a CourtListener API URL.

    E.g., "https://www.courtlistener.com/api/rest/v4/opinions/12345/" -> 12345
    """
    match = re.search(r"/(\d+)/?$", url)
    if match:
        return int(match.group(1))
    return None
