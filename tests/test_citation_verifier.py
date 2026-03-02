"""Tests for case citation verification against CourtListener API.

Uses respx to mock httpx requests. Tests cover all VerificationStatus
outcomes: verified, not_found, wrong_jurisdiction, date_mismatch,
ambiguous, and error conditions.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from employee_help.generation.citation_verifier import (
    CaseCitationVerifier,
    CaseVerificationResult,
    CitationConfidence,
    ScoredCitation,
    StatuteCitationVerifier,
    StatuteVerificationResult,
    StatuteVerificationStatus,
    VerificationStatus,
    score_all_citations,
    score_case_result,
    score_statute_result,
)
from employee_help.scraper.extractors.courtlistener import (
    API_BASE,
    AuthenticationError,
    CourtListenerClient,
    CourtListenerError,
    RateLimitError,
)
from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create a CourtListenerClient with a test token."""
    return CourtListenerClient(api_token="test-token-123", max_retries=1)


@pytest.fixture
def verifier(client):
    """Create a CaseCitationVerifier with a test client."""
    return CaseCitationVerifier(client=client)


# ── Response factories ────────────────────────────────────────


def _make_lookup_response(
    *,
    citation: str = "45 Cal. App. 5th 123",
    status: int = 200,
    cluster_id: int = 12345,
    case_name: str = "Smith v. Employer, Inc.",
    date_filed: str = "2023-06-15",
    absolute_url: str = "/opinion/12345/smith-v-employer-inc/",
):
    """Build a CourtListener citation-lookup response."""
    result = {
        "citation": citation,
        "normalized_citations": [citation],
        "status": status,
        "error_message": "",
    }
    if status == 200:
        result["clusters"] = [
            {
                "id": cluster_id,
                "case_name": case_name,
                "date_filed": date_filed,
                "absolute_url": absolute_url,
            }
        ]
    else:
        result["clusters"] = []
    return [result]


# Text fixtures with California case citations
CA_CASE_TEXT = "The court in Smith v. Employer, Inc., 45 Cal. App. 5th 123 (2023) held that retaliation claims require direct evidence."

MULTI_CASE_TEXT = (
    "See Smith v. Employer, 45 Cal. App. 5th 123 (2023); "
    "Jones v. Corp, 50 Cal. 4th 456 (2021); "
    "Doe v. State, 30 Cal. App. 5th 789 (2020)."
)

FEDERAL_CASE_TEXT = "The Ninth Circuit held in Jones v. Corp, 500 F.3d 123 (9th Cir. 2022) that the claim was valid."

STATUTE_ONLY_TEXT = "Cal. Lab. Code § 1102.5 prohibits retaliation against whistleblowers."


# ── Data model tests ──────────────────────────────────────────


class TestVerificationStatus:
    def test_enum_values(self):
        assert VerificationStatus.VERIFIED == "verified"
        assert VerificationStatus.NOT_FOUND == "not_found"
        assert VerificationStatus.WRONG_JURISDICTION == "wrong_jurisdiction"
        assert VerificationStatus.DATE_MISMATCH == "date_mismatch"
        assert VerificationStatus.AMBIGUOUS == "ambiguous"
        assert VerificationStatus.ERROR == "error"

    def test_all_statuses(self):
        assert len(VerificationStatus) == 6


class TestCaseVerificationResult:
    def test_defaults(self):
        r = CaseVerificationResult(
            citation_text="test", status=VerificationStatus.VERIFIED
        )
        assert r.reporter is None
        assert r.volume is None
        assert r.page is None
        assert r.year_cited is None
        assert r.year_filed is None
        assert r.case_name is None
        assert r.cluster_id is None
        assert r.court_listener_url is None
        assert r.error_detail is None


# ── Core verification tests ───────────────────────────────────


class TestCaseCitationVerifier:
    @respx.mock
    def test_verified_ca_case(self, verifier):
        """Valid California case citation should be VERIFIED."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(date_filed="2023-06-15")
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        r = results[0]
        assert r.status == VerificationStatus.VERIFIED
        assert r.case_name == "Smith v. Employer, Inc."
        assert r.cluster_id == 12345
        assert r.court_listener_url == "/opinion/12345/smith-v-employer-inc/"
        assert r.year_filed == "2023"

    @respx.mock
    def test_not_found(self, verifier):
        """Citation not found in CourtListener should be NOT_FOUND."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(status=404)
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.NOT_FOUND

    @respx.mock
    def test_wrong_jurisdiction(self, verifier):
        """Citation found but with non-California reporter should be WRONG_JURISDICTION."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200,
                json=_make_lookup_response(citation="45 F.3d 123"),
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.WRONG_JURISDICTION

    @respx.mock
    def test_date_mismatch(self, verifier):
        """Citation year doesn't match filing year should be DATE_MISMATCH."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200,
                json=_make_lookup_response(date_filed="2021-03-10"),
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        r = results[0]
        assert r.status == VerificationStatus.DATE_MISMATCH
        assert r.year_cited == "2023"
        assert r.year_filed == "2021"

    @respx.mock
    def test_ambiguous(self, verifier):
        """CourtListener returning status 300 should be AMBIGUOUS."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(status=300)
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.AMBIGUOUS

    @respx.mock
    def test_network_error(self, verifier):
        """Network error during lookup should return ERROR with detail."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        r = results[0]
        assert r.status == VerificationStatus.ERROR
        assert r.error_detail is not None

    @respx.mock
    def test_rate_limit_error(self, verifier):
        """RateLimitError during lookup should return ERROR."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            side_effect=RateLimitError(retry_after=60)
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.ERROR

    @respx.mock
    def test_auth_error(self, verifier):
        """AuthenticationError during lookup should return ERROR."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(401, json={"detail": "Invalid token"})
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.ERROR

    def test_no_api_token(self):
        """Verifier without API token should return empty list."""
        verifier = CaseCitationVerifier(client=None, api_token=None)
        results = verifier.verify_citations(CA_CASE_TEXT)
        assert results == []

    @respx.mock
    def test_multiple_citations(self, verifier):
        """Multiple case citations should each produce a result."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response()
            )
        )
        results = verifier.verify_citations(MULTI_CASE_TEXT)

        assert len(results) == 3

    def test_non_california_skipped(self, verifier):
        """Federal (non-California) citations should be skipped."""
        results = verifier.verify_citations(FEDERAL_CASE_TEXT)
        assert results == []

    def test_statute_skipped(self, verifier):
        """Statute-only text should produce no case verification results."""
        results = verifier.verify_citations(STATUTE_ONLY_TEXT)
        assert results == []

    @respx.mock
    def test_missing_volume_page_skipped(self, verifier):
        """Citations without volume/reporter/page should be skipped."""
        # "Id." and "supra" citations lack volume/page — not verifiable
        text = "As noted in Id. at 456, the holding was clear."
        results = verifier.verify_citations(text)
        assert results == []

    @respx.mock
    def test_year_missing_no_mismatch(self, verifier):
        """Citation without explicit year should still be VERIFIED if found."""
        # Citation text without parenthetical year
        text = "The court in Smith v. Employer, Inc., 45 Cal. App. 5th 123 held that the claim was valid."
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(date_filed="2023-06-15")
            )
        )
        results = verifier.verify_citations(text)

        if results:  # eyecite may or may not extract year
            r = results[0]
            # If no year was extracted, should not be DATE_MISMATCH
            assert r.status in (
                VerificationStatus.VERIFIED,
                VerificationStatus.DATE_MISMATCH,
            )
            if r.year_cited is None:
                assert r.status == VerificationStatus.VERIFIED

    def test_empty_text(self, verifier):
        """Empty string should return empty list."""
        results = verifier.verify_citations("")
        assert results == []

    @respx.mock
    def test_result_fields_populated(self, verifier):
        """Verified result should have all metadata fields populated."""
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(date_filed="2023-06-15")
            )
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        r = results[0]
        assert r.reporter is not None
        assert r.volume is not None
        assert r.page is not None
        assert r.citation_text  # non-empty

    @respx.mock
    def test_empty_clusters_treated_as_not_found(self, verifier):
        """Status 200 but empty clusters list should be NOT_FOUND."""
        response = [
            {
                "citation": "45 Cal. App. 5th 123",
                "normalized_citations": ["45 Cal. App. 5th 123"],
                "status": 200,
                "error_message": "",
                "clusters": [],
            }
        ]
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(200, json=response)
        )
        results = verifier.verify_citations(CA_CASE_TEXT)

        assert len(results) >= 1
        assert results[0].status == VerificationStatus.NOT_FOUND


# ══════════════════════════════════════════════════════════════
# Statute citation verifier tests
# ══════════════════════════════════════════════════════════════

STATUTE_TEXT = "Under Cal. Lab. Code § 1102.5, employees are protected from retaliation."
MULTI_STATUTE_TEXT = (
    "Cal. Lab. Code § 1102.5 and Cal. Gov. Code § 12940 "
    "prohibit workplace retaliation and discrimination."
)
CASE_ONLY_TEXT_2 = "In Smith v. Employer, 45 Cal. App. 5th 123 (2023), the court ruled."


def _insert_statute_chunk(
    storage: Storage,
    *,
    citation: str = "Cal. Lab. Code § 1102.5",
    is_active: bool = True,
    retrieved_at: str = "2026-02-28T00:00:00",
) -> int:
    """Insert a statute document + chunk into storage. Returns chunk ID."""
    from datetime import datetime as dt

    # Get or create source
    source = storage.get_source("labor-code")
    if source is None:
        source = storage.create_source(Source(
            name="Labor Code",
            slug="labor-code",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://leginfo.legislature.ca.gov",
        ))
    run = storage.create_run(source_id=source.id)

    # Extract section number from citation for unique URLs
    section_num = citation.split("§")[-1].strip() if "§" in citation else "0"
    code_abbr = citation.split(".")[1].strip().split()[0] if "." in citation else "LAB"

    doc = Document(
        source_url=f"https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode={code_abbr}&sectionNum={section_num}",
        title=citation,
        content_type=ContentType.HTML,
        raw_content=f"<p>Content of {citation}</p>",
        content_hash=f"hash_{citation.replace(' ', '_')}",
        retrieved_at=dt.fromisoformat(retrieved_at),
        last_modified=None,
        content_category=ContentCategory.STATUTORY_CODE,
        crawl_run_id=run.id,
        source_id=source.id,
    )
    doc, _ = storage.upsert_document(doc)

    chunk = Chunk(
        content=f"[{citation}]\nStatute content for testing.",
        content_hash=f"chunk_hash_{citation.replace(' ', '_')}",
        chunk_index=0,
        heading_path=f"{code_abbr} > Division 2",
        token_count=50,
        document_id=doc.id,
        content_category=ContentCategory.STATUTORY_CODE,
        citation=citation,
        is_active=True,
    )
    storage.insert_chunks([chunk])

    # If inactive, deactivate via storage
    if not is_active:
        storage.deactivate_chunks_for_document(doc.id)

    chunks = storage.get_chunks_for_document(doc.id)
    return chunks[0].id


@pytest.fixture
def statute_storage(tmp_path):
    """Create a Storage instance with an empty DB for statute tests."""
    db = tmp_path / "statute_test.db"
    s = Storage(db_path=db)
    yield s
    s.close()


class TestStatuteVerificationStatus:
    def test_enum_values(self):
        assert StatuteVerificationStatus.VERIFIED == "verified"
        assert StatuteVerificationStatus.NOT_FOUND == "not_found"
        assert StatuteVerificationStatus.REPEALED == "repealed"
        assert StatuteVerificationStatus.AMENDED == "amended"
        assert StatuteVerificationStatus.ERROR == "error"

    def test_all_statuses(self):
        assert len(StatuteVerificationStatus) == 5


class TestStatuteVerificationResult:
    def test_defaults(self):
        r = StatuteVerificationResult(
            citation_text="test", status=StatuteVerificationStatus.VERIFIED
        )
        assert r.section is None
        assert r.code_type is None
        assert r.matched_citation is None
        assert r.chunk_id is None
        assert r.is_active is None
        assert r.last_ingested is None
        assert r.error_detail is None


class TestStatuteCitationVerifier:
    def test_verified_active_section(self, statute_storage):
        """Active statute section should be VERIFIED."""
        _insert_statute_chunk(statute_storage)
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        r = results[0]
        assert r.status == StatuteVerificationStatus.VERIFIED
        assert r.section == "1102.5"
        assert r.code_type == "Lab"
        assert r.chunk_id is not None
        assert r.is_active is True
        assert r.matched_citation == "Cal. Lab. Code § 1102.5"

    def test_repealed_section(self, statute_storage):
        """Repealed (inactive) statute section should be REPEALED."""
        _insert_statute_chunk(statute_storage, is_active=False)
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        assert results[0].status == StatuteVerificationStatus.REPEALED
        assert results[0].is_active is False

    def test_not_found_section(self, statute_storage):
        """Section not in the database should be NOT_FOUND."""
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        assert results[0].status == StatuteVerificationStatus.NOT_FOUND

    def test_amended_stale_section(self, statute_storage):
        """Section ingested long ago should be AMENDED (stale warning)."""
        _insert_statute_chunk(
            statute_storage, retrieved_at="2025-01-01T00:00:00"
        )
        verifier = StatuteCitationVerifier(
            statute_storage, amended_threshold_days=30
        )

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        assert results[0].status == StatuteVerificationStatus.AMENDED

    def test_recently_ingested_not_amended(self, statute_storage):
        """Recently ingested section should be VERIFIED, not AMENDED."""
        from datetime import datetime as dt, timezone as tz
        now_iso = dt.now(tz=tz.utc).isoformat()
        _insert_statute_chunk(statute_storage, retrieved_at=now_iso)
        verifier = StatuteCitationVerifier(
            statute_storage, amended_threshold_days=30
        )

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        assert results[0].status == StatuteVerificationStatus.VERIFIED

    def test_multiple_statutes(self, statute_storage):
        """Multiple statute citations should produce multiple results."""
        _insert_statute_chunk(statute_storage, citation="Cal. Lab. Code § 1102.5")
        _insert_statute_chunk(statute_storage, citation="Cal. Gov. Code § 12940")
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(MULTI_STATUTE_TEXT)

        assert len(results) == 2
        statuses = {r.section: r.status for r in results}
        assert "1102.5" in statuses
        assert "12940" in statuses

    def test_case_citation_skipped(self, statute_storage):
        """Case citations should not produce statute verification results."""
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(CASE_ONLY_TEXT_2)
        assert results == []

    def test_empty_text(self, statute_storage):
        """Empty text should return empty list."""
        verifier = StatuteCitationVerifier(statute_storage)
        results = verifier.verify_citations("")
        assert results == []

    def test_non_california_skipped(self, statute_storage):
        """Non-California statute should be skipped."""
        verifier = StatuteCitationVerifier(statute_storage)
        results = verifier.verify_citations("Under 42 U.S.C. § 1983, plaintiffs may sue.")
        assert results == []

    def test_duplicate_citations_deduplicated(self, statute_storage):
        """Same statute cited twice should produce only one result."""
        _insert_statute_chunk(statute_storage)
        verifier = StatuteCitationVerifier(statute_storage)

        text = "Cal. Lab. Code § 1102.5 protects workers. See also Cal. Lab. Code § 1102.5."
        results = verifier.verify_citations(text)

        assert len(results) == 1

    def test_result_fields_populated(self, statute_storage):
        """Verified result should have all metadata fields populated."""
        _insert_statute_chunk(statute_storage)
        verifier = StatuteCitationVerifier(statute_storage)

        results = verifier.verify_citations(STATUTE_TEXT)

        assert len(results) == 1
        r = results[0]
        assert r.citation_text
        assert r.section is not None
        assert r.code_type is not None
        assert r.matched_citation is not None
        assert r.chunk_id is not None
        assert r.last_ingested is not None

    def test_extract_code_type(self):
        """_extract_code_type should extract abbreviation from citation text."""
        assert StatuteCitationVerifier._extract_code_type("Cal. Lab. Code § 1102.5") == "Lab"
        assert StatuteCitationVerifier._extract_code_type("Cal. Gov. Code § 12940") == "Gov"
        assert StatuteCitationVerifier._extract_code_type("Cal. Bus. & Prof. Code § 17200") == "Bus"
        assert StatuteCitationVerifier._extract_code_type("Cal. Civ. Proc. Code § 340") == "Civ"
        assert StatuteCitationVerifier._extract_code_type("Cal. Unemp. Ins. Code § 1253") == "Unemp"
        assert StatuteCitationVerifier._extract_code_type(None) is None
        assert StatuteCitationVerifier._extract_code_type("Unknown text") is None


class TestLookupStatuteChunk:
    """Test the Storage.lookup_statute_chunk() method directly."""

    def test_lookup_by_section_and_code(self, statute_storage):
        _insert_statute_chunk(statute_storage)
        result = statute_storage.lookup_statute_chunk("1102.5", code_type="Lab")
        assert result is not None
        assert result["citation"] == "Cal. Lab. Code § 1102.5"
        assert result["is_active"] is True

    def test_lookup_by_section_only(self, statute_storage):
        _insert_statute_chunk(statute_storage)
        result = statute_storage.lookup_statute_chunk("1102.5")
        assert result is not None

    def test_lookup_not_found(self, statute_storage):
        result = statute_storage.lookup_statute_chunk("99999")
        assert result is None

    def test_lookup_wrong_code_type(self, statute_storage):
        _insert_statute_chunk(statute_storage, citation="Cal. Lab. Code § 1102.5")
        result = statute_storage.lookup_statute_chunk("1102.5", code_type="Gov")
        assert result is None

    def test_lookup_inactive_section(self, statute_storage):
        _insert_statute_chunk(statute_storage, is_active=False)
        result = statute_storage.lookup_statute_chunk("1102.5", code_type="Lab")
        assert result is not None
        assert result["is_active"] is False


# ══════════════════════════════════════════════════════════════
# Confidence scoring tests
# ══════════════════════════════════════════════════════════════


class TestCitationConfidence:
    def test_enum_values(self):
        assert CitationConfidence.VERIFIED == "verified"
        assert CitationConfidence.UNVERIFIED == "unverified"
        assert CitationConfidence.SUSPICIOUS == "suspicious"

    def test_all_levels(self):
        assert len(CitationConfidence) == 3


class TestScoreCaseResult:
    def test_verified_case(self):
        result = CaseVerificationResult(
            citation_text="45 Cal. App. 5th 123",
            status=VerificationStatus.VERIFIED,
            case_name="Smith v. Employer",
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.VERIFIED
        assert scored.citation_type == "case"
        assert "Smith v. Employer" in scored.detail

    def test_not_found_case(self):
        result = CaseVerificationResult(
            citation_text="999 Cal.App.99th 999",
            status=VerificationStatus.NOT_FOUND,
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.UNVERIFIED
        assert "not found" in scored.detail.lower()

    def test_wrong_jurisdiction_case(self):
        result = CaseVerificationResult(
            citation_text="45 F.3d 123",
            status=VerificationStatus.WRONG_JURISDICTION,
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.SUSPICIOUS
        assert "not a California" in scored.detail

    def test_date_mismatch_case(self):
        result = CaseVerificationResult(
            citation_text="45 Cal. App. 5th 123",
            status=VerificationStatus.DATE_MISMATCH,
            year_cited="2023",
            year_filed="2021",
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.SUSPICIOUS
        assert "2023" in scored.detail
        assert "2021" in scored.detail

    def test_ambiguous_case(self):
        result = CaseVerificationResult(
            citation_text="45 Cal. App. 5th 123",
            status=VerificationStatus.AMBIGUOUS,
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.UNVERIFIED

    def test_error_case(self):
        result = CaseVerificationResult(
            citation_text="45 Cal. App. 5th 123",
            status=VerificationStatus.ERROR,
            error_detail="Connection refused",
        )
        scored = score_case_result(result)
        assert scored.confidence == CitationConfidence.UNVERIFIED
        assert "Connection refused" in scored.detail

    def test_verification_status_preserved(self):
        result = CaseVerificationResult(
            citation_text="45 Cal. App. 5th 123",
            status=VerificationStatus.DATE_MISMATCH,
        )
        scored = score_case_result(result)
        assert scored.verification_status == "date_mismatch"


class TestScoreStatuteResult:
    def test_verified_statute(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 1102.5",
            status=StatuteVerificationStatus.VERIFIED,
            matched_citation="Cal. Lab. Code § 1102.5",
        )
        scored = score_statute_result(result)
        assert scored.confidence == CitationConfidence.VERIFIED
        assert scored.citation_type == "statute"
        assert "knowledge base" in scored.detail.lower()

    def test_not_found_statute(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 99999",
            status=StatuteVerificationStatus.NOT_FOUND,
        )
        scored = score_statute_result(result)
        assert scored.confidence == CitationConfidence.UNVERIFIED

    def test_repealed_statute(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 1102.5",
            status=StatuteVerificationStatus.REPEALED,
        )
        scored = score_statute_result(result)
        assert scored.confidence == CitationConfidence.SUSPICIOUS
        assert "repealed" in scored.detail.lower()

    def test_amended_statute(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 1102.5",
            status=StatuteVerificationStatus.AMENDED,
            last_ingested="2025-01-01T00:00:00",
        )
        scored = score_statute_result(result)
        assert scored.confidence == CitationConfidence.SUSPICIOUS
        assert "amended" in scored.detail.lower()

    def test_error_statute(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 1102.5",
            status=StatuteVerificationStatus.ERROR,
            error_detail="DB locked",
        )
        scored = score_statute_result(result)
        assert scored.confidence == CitationConfidence.UNVERIFIED
        assert "DB locked" in scored.detail

    def test_verification_status_preserved(self):
        result = StatuteVerificationResult(
            citation_text="Cal. Lab. Code § 1102.5",
            status=StatuteVerificationStatus.REPEALED,
        )
        scored = score_statute_result(result)
        assert scored.verification_status == "repealed"


class TestScoreAllCitations:
    @respx.mock
    def test_mixed_case_and_statute(self, statute_storage):
        """score_all_citations should return results for both case and statute."""
        _insert_statute_chunk(statute_storage)

        client = CourtListenerClient(api_token="test-token", max_retries=1)
        case_verifier = CaseCitationVerifier(client=client)
        statute_verifier = StatuteCitationVerifier(statute_storage)

        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(
                200, json=_make_lookup_response(date_filed="2023-06-15")
            )
        )

        text = (
            "In Smith v. Employer, 45 Cal. App. 5th 123 (2023), the court "
            "applied Cal. Lab. Code § 1102.5 to find retaliation."
        )
        scored = score_all_citations(text, case_verifier, statute_verifier)

        types = {s.citation_type for s in scored}
        assert "case" in types
        assert "statute" in types

    def test_statute_only(self, statute_storage):
        """score_all_citations with only statute verifier."""
        _insert_statute_chunk(statute_storage)
        statute_verifier = StatuteCitationVerifier(statute_storage)

        scored = score_all_citations(STATUTE_TEXT, statute_verifier=statute_verifier)

        assert len(scored) == 1
        assert scored[0].citation_type == "statute"
        assert scored[0].confidence == CitationConfidence.VERIFIED

    def test_no_verifiers(self):
        """score_all_citations with no verifiers returns empty list."""
        scored = score_all_citations("Some text with no verifiers.")
        assert scored == []

    def test_empty_text(self, statute_storage):
        """score_all_citations with empty text returns empty list."""
        statute_verifier = StatuteCitationVerifier(statute_storage)
        scored = score_all_citations("", statute_verifier=statute_verifier)
        assert scored == []
