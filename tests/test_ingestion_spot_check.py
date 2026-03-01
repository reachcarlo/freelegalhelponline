"""Spot-check validation tests for the ingested knowledge base.

These tests run against the LIVE database at data/employee_help.db.
They verify data integrity, content quality, and citation accuracy
by sampling real records and checking them against known expectations.

Mark: @pytest.mark.spot_check — skipped unless explicitly selected.
"""

from __future__ import annotations

import random
import re
import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path("data/employee_help.db")

pytestmark = pytest.mark.spot_check


@pytest.fixture(scope="module")
def db():
    """Connect to the live database."""
    if not DB_PATH.exists():
        pytest.skip("Live database not found at data/employee_help.db")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ── 1. Source completeness ────────────────────────────────────

EXPECTED_SOURCES = {
    "labor_code": "statutory_code",
    "gov_code_feha": "statutory_code",
    "gov_code_whistleblower": "statutory_code",
    "unemp_ins_code": "statutory_code",
    "bus_prof_code": "statutory_code",
    "ccp": "statutory_code",
    "caci": "statutory_code",
    "dir": "agency",
    "edd": "agency",
    "calhr": "agency",
    "crd": "agency",
}


class TestSourceCompleteness:
    def test_all_expected_sources_present(self, db):
        """All 11 configured sources exist in the database."""
        rows = db.execute("SELECT slug, source_type FROM sources").fetchall()
        slugs = {r["slug"]: r["source_type"] for r in rows}
        for slug, expected_type in EXPECTED_SOURCES.items():
            assert slug in slugs, f"Missing source: {slug}"
            assert slugs[slug] == expected_type, (
                f"Source {slug}: expected type '{expected_type}', got '{slugs[slug]}'"
            )

    def test_minimum_document_counts(self, db):
        """Each source has a reasonable minimum number of documents."""
        minimums = {
            "labor_code": 2000,
            "gov_code_feha": 4000,
            "gov_code_whistleblower": 7000,
            "unemp_ins_code": 700,
            "bus_prof_code": 400,
            "ccp": 3000,
            "caci": 300,
            "dir": 200,
            "edd": 150,
            "calhr": 250,
            "crd": 5,
        }
        for slug, min_docs in minimums.items():
            row = db.execute(
                """SELECT COUNT(*) as cnt FROM documents d
                   JOIN sources s ON d.source_id = s.id
                   WHERE s.slug = ?""",
                (slug,),
            ).fetchone()
            assert row["cnt"] >= min_docs, (
                f"{slug}: expected >= {min_docs} documents, got {row['cnt']}"
            )

    def test_minimum_chunk_counts(self, db):
        """Each source has a reasonable minimum number of active chunks."""
        minimums = {
            "labor_code": 2500,
            "gov_code_feha": 4500,
            "gov_code_whistleblower": 7500,
            "unemp_ins_code": 800,
            "bus_prof_code": 400,
            "ccp": 3000,
            "caci": 300,
            "dir": 1500,
            "edd": 350,
            "calhr": 1000,
            "crd": 5,
        }
        for slug, min_chunks in minimums.items():
            row = db.execute(
                """SELECT COUNT(*) as cnt FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   JOIN sources s ON d.source_id = s.id
                   WHERE s.slug = ? AND c.is_active = 1""",
                (slug,),
            ).fetchone()
            assert row["cnt"] >= min_chunks, (
                f"{slug}: expected >= {min_chunks} active chunks, got {row['cnt']}"
            )


# ── 2. Known statutory sections exist ────────────────────────

KNOWN_SECTIONS = [
    # (slug, citation_pattern, description)
    ("labor_code", r"Cal\. Lab\. Code § 200\b", "Wages definition"),
    ("labor_code", r"Cal\. Lab\. Code § 1102\.5\b", "Whistleblower protection"),
    ("labor_code", r"Cal\. Lab\. Code § 226\b", "Wage statement requirements"),
    ("labor_code", r"Cal\. Lab\. Code § 510\b", "Overtime definition"),
    ("labor_code", r"Cal\. Lab\. Code § 2802\b", "Employee expense reimbursement"),
    ("gov_code_feha", r"Cal\. Gov\. Code § 12940\b", "FEHA unlawful practices"),
    ("gov_code_feha", r"Cal\. Gov\. Code § 12945\b", "Pregnancy discrimination"),
    ("gov_code_feha", r"Cal\. Gov\. Code § 12926\b", "FEHA definitions"),
    ("gov_code_whistleblower", r"Cal\. Gov\. Code § 8547\b", "State employee whistleblower"),
    ("unemp_ins_code", r"Cal\. Unemp\. Ins\. Code § 1256\b", "Disqualification for cause"),
    ("unemp_ins_code", r"Cal\. Unemp\. Ins\. Code § 2601\b", "SDI benefits"),
    ("bus_prof_code", r"Cal\. Bus\. & Prof\. Code § 16600\b", "Non-compete void"),
    ("bus_prof_code", r"Cal\. Bus\. & Prof\. Code § 17200\b", "Unfair business practices"),
    ("ccp", r"Cal\. Code Civ\. Proc\. § 340\b", "Statute of limitations"),
    ("ccp", r"Cal\. Code Civ\. Proc\. § 425\.16\b", "Anti-SLAPP"),
    ("ccp", r"Cal\. Code Civ\. Proc\. § 1021\.5\b", "Private attorney general"),
]


class TestKnownSections:
    @pytest.mark.parametrize(
        "slug,citation_re,desc",
        KNOWN_SECTIONS,
        ids=[f"{s[0]}:{s[2]}" for s in KNOWN_SECTIONS],
    )
    def test_known_section_exists(self, db, slug, citation_re, desc):
        """A known statutory section exists with matching citation."""
        rows = db.execute(
            """SELECT c.citation, c.content, c.token_count
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = ? AND c.citation IS NOT NULL AND c.is_active = 1""",
            (slug,),
        ).fetchall()

        matches = [r for r in rows if re.search(citation_re, r["citation"])]
        assert len(matches) >= 1, (
            f"No chunk found for {desc} (pattern: {citation_re}) in {slug}"
        )
        # Verify the chunk has real content
        for m in matches:
            assert len(m["content"].strip()) > 20, (
                f"Chunk for {desc} has suspiciously short content: {m['content'][:50]!r}"
            )
            assert m["token_count"] > 0, f"Chunk for {desc} has 0 tokens"


# ── 3. Statutory citation format consistency ──────────────────

CITATION_FORMATS = {
    "labor_code": r"^Cal\. Lab\. Code § [\d.]+",
    "gov_code_feha": r"^Cal\. Gov\. Code § [\d.]+",
    "gov_code_whistleblower": r"^Cal\. Gov\. Code § [\d.]+",
    "unemp_ins_code": r"^Cal\. Unemp\. Ins\. Code § [\d.]+",
    "bus_prof_code": r"^Cal\. Bus\. & Prof\. Code § [\d.]+",
    "ccp": r"^Cal\. Code Civ\. Proc\. § [\d.]+",
}


class TestCitationConsistency:
    @pytest.mark.parametrize("slug,expected_re", CITATION_FORMATS.items())
    def test_all_citations_match_format(self, db, slug, expected_re):
        """100% of statutory chunks have properly formatted citations."""
        rows = db.execute(
            """SELECT c.citation FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = ? AND c.is_active = 1""",
            (slug,),
        ).fetchall()

        assert len(rows) > 0, f"No chunks found for {slug}"

        bad = [r["citation"] for r in rows if not re.match(expected_re, r["citation"] or "")]
        assert len(bad) == 0, (
            f"{slug}: {len(bad)}/{len(rows)} citations don't match format. "
            f"Sample bad: {bad[:5]}"
        )

    def test_agency_chunks_have_no_citations(self, db):
        """Agency source chunks should have NULL citations (not statutory)."""
        for slug in ("dir", "edd", "calhr"):
            row = db.execute(
                """SELECT COUNT(*) as cnt FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   JOIN sources s ON d.source_id = s.id
                   WHERE s.slug = ? AND c.citation IS NOT NULL AND c.is_active = 1""",
                (slug,),
            ).fetchone()
            assert row["cnt"] == 0, (
                f"Agency source {slug} has {row['cnt']} chunks with citations (should be 0)"
            )


# ── 4. Content quality spot-checks ───────────────────────────


class TestContentQuality:
    def test_no_html_tags_in_statutory_content(self, db):
        """Statutory chunk content should be plain text, not raw HTML."""
        rows = db.execute(
            """SELECT c.content, c.citation, s.slug
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'statutory_code' AND c.is_active = 1
               ORDER BY RANDOM() LIMIT 50""",
        ).fetchall()

        html_tag_re = re.compile(r"<(?:div|span|p|table|br|html|body|head)\b", re.IGNORECASE)
        bad = [(r["slug"], r["citation"]) for r in rows if html_tag_re.search(r["content"])]
        assert len(bad) == 0, (
            f"Found {len(bad)} statutory chunks with HTML tags: {bad[:5]}"
        )

    def test_no_empty_content_chunks(self, db):
        """No chunks should have empty or whitespace-only content."""
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM chunks
               WHERE is_active = 1 AND (content IS NULL OR TRIM(content) = '')""",
        ).fetchone()
        assert row["cnt"] == 0, f"Found {row['cnt']} empty chunks"

    def test_chunk_index_sequential(self, db):
        """Chunk indices should be sequential (0, 1, 2, ...) within each document."""
        # Sample 100 documents and check their chunk ordering
        docs = db.execute(
            """SELECT DISTINCT document_id FROM chunks
               WHERE is_active = 1
               ORDER BY RANDOM() LIMIT 100""",
        ).fetchall()

        bad_docs = []
        for doc in docs:
            chunks = db.execute(
                """SELECT chunk_index FROM chunks
                   WHERE document_id = ? AND is_active = 1
                   ORDER BY chunk_index""",
                (doc["document_id"],),
            ).fetchall()
            indices = [c["chunk_index"] for c in chunks]
            expected = list(range(len(indices)))
            if indices != expected:
                bad_docs.append((doc["document_id"], indices))

        assert len(bad_docs) == 0, (
            f"{len(bad_docs)} documents have non-sequential chunk indices. "
            f"Sample: {bad_docs[:3]}"
        )

    def test_statutory_content_contains_legal_language(self, db):
        """Random statutory chunks should contain recognizable legal text."""
        rows = db.execute(
            """SELECT c.content, c.citation, s.slug
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'statutory_code' AND c.is_active = 1
                 AND c.token_count > 50
               ORDER BY RANDOM() LIMIT 30""",
        ).fetchall()

        # At least 80% should contain common legal terms
        legal_terms = re.compile(
            r"\b(shall|section|subdivision|pursuant|notwithstanding|employer|employee|"
            r"person|code|law|act|state|california|court|chapter|division|part)\b",
            re.IGNORECASE,
        )
        matches = sum(1 for r in rows if legal_terms.search(r["content"]))
        pct = matches / len(rows) * 100
        assert pct >= 80, (
            f"Only {pct:.0f}% of sampled statutory chunks contain legal terms (expected >= 80%)"
        )

    def test_agency_content_is_informational(self, db):
        """Agency chunks should contain informational/guidance language."""
        rows = db.execute(
            """SELECT c.content, s.slug
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'agency' AND c.is_active = 1
                 AND c.token_count > 50
               ORDER BY RANDOM() LIMIT 30""",
        ).fetchall()

        if not rows:
            pytest.skip("No agency chunks with >50 tokens found")

        # At least 70% should contain informational terms
        info_terms = re.compile(
            r"\b(employee|employer|rights|information|contact|department|"
            r"state|california|benefit|claim|work|law|wage|labor|leave)\b",
            re.IGNORECASE,
        )
        matches = sum(1 for r in rows if info_terms.search(r["content"]))
        pct = matches / len(rows) * 100
        assert pct >= 70, (
            f"Only {pct:.0f}% of sampled agency chunks contain expected terms (expected >= 70%)"
        )


# ── 5. Content category integrity ────────────────────────────


VALID_STATUTORY_CATEGORIES = {"statutory_code", "jury_instruction"}


class TestContentCategory:
    def test_statutory_chunks_have_statutory_category(self, db):
        """All chunks under statutory sources have a valid statutory content_category."""
        placeholders = ",".join(f"'{c}'" for c in VALID_STATUTORY_CATEGORIES)
        row = db.execute(
            f"""SELECT COUNT(*) as cnt FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'statutory_code'
                 AND c.content_category NOT IN ({placeholders})
                 AND c.is_active = 1""",
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} statutory chunks with wrong content_category"
        )

    def test_agency_chunks_have_agency_category(self, db):
        """All chunks under agency sources have an agency-type content_category."""
        agency_categories = {"agency_guidance", "fact_sheet", "faq", "poster", "regulation"}
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'agency'
                 AND c.content_category = 'statutory_code'
                 AND c.is_active = 1""",
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} agency chunks wrongly categorized as 'statutory_code'"
        )


# ── 6. Document-chunk referential integrity ───────────────────


class TestReferentialIntegrity:
    def test_no_orphaned_chunks(self, db):
        """Every chunk references a valid document."""
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM chunks c
               LEFT JOIN documents d ON c.document_id = d.id
               WHERE d.id IS NULL""",
        ).fetchone()
        assert row["cnt"] == 0, f"Found {row['cnt']} orphaned chunks"

    def test_no_orphaned_documents(self, db):
        """Every document references a valid source."""
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM documents d
               LEFT JOIN sources s ON d.source_id = s.id
               WHERE s.id IS NULL""",
        ).fetchone()
        assert row["cnt"] == 0, f"Found {row['cnt']} orphaned documents"

    def test_all_documents_have_chunks(self, db):
        """Every document has at least one chunk."""
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM documents d
               LEFT JOIN chunks c ON c.document_id = d.id
               WHERE c.id IS NULL""",
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} documents with zero chunks"
        )

    def test_no_duplicate_chunks(self, db):
        """No exact duplicate chunks within the same document."""
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM (
                SELECT document_id, content_hash, COUNT(*) as dupes
                FROM chunks WHERE is_active = 1
                GROUP BY document_id, content_hash
                HAVING dupes > 1
            )""",
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} duplicate chunk groups within same document"
        )


# ── 7. Heading path structure ─────────────────────────────────


class TestHeadingPaths:
    def test_statutory_chunks_have_heading_paths(self, db):
        """Statutory chunks should have non-empty heading_path (hierarchy)."""
        rows = db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN c.heading_path IS NOT NULL AND TRIM(c.heading_path) != '' THEN 1 ELSE 0 END) as with_path
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'statutory_code' AND c.is_active = 1""",
        ).fetchone()
        pct = rows["with_path"] / rows["total"] * 100
        assert pct >= 95, (
            f"Only {pct:.1f}% of statutory chunks have heading_path (expected >= 95%)"
        )

    def test_heading_path_contains_hierarchy(self, db):
        """Sample statutory heading_paths should contain hierarchy markers."""
        rows = db.execute(
            """SELECT c.heading_path, s.slug
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.source_type = 'statutory_code' AND c.is_active = 1
                 AND c.heading_path IS NOT NULL AND TRIM(c.heading_path) != ''
               ORDER BY RANDOM() LIMIT 30""",
        ).fetchall()

        hierarchy_re = re.compile(r"(Division|Chapter|Part|Article|Title)", re.IGNORECASE)
        matches = sum(1 for r in rows if hierarchy_re.search(r["heading_path"]))
        pct = matches / len(rows) * 100
        assert pct >= 70, (
            f"Only {pct:.0f}% of heading_paths contain hierarchy terms (expected >= 70%). "
            f"Sample: {[r['heading_path'] for r in rows[:5]]}"
        )


# ── 8. Token count sanity ────────────────────────────────────


class TestTokenSanity:
    def test_no_zero_token_chunks(self, db):
        """No active chunks should have 0 tokens."""
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE is_active = 1 AND token_count = 0",
        ).fetchone()
        assert row["cnt"] == 0, f"Found {row['cnt']} zero-token chunks"

    def test_statutory_avg_tokens_reasonable(self, db):
        """Statutory chunks should average 100-1000 tokens."""
        for slug in ("labor_code", "gov_code_feha", "ccp"):
            row = db.execute(
                """SELECT AVG(c.token_count) as avg_tok
                   FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   JOIN sources s ON d.source_id = s.id
                   WHERE s.slug = ? AND c.is_active = 1""",
                (slug,),
            ).fetchone()
            avg = row["avg_tok"]
            assert 100 <= avg <= 1000, (
                f"{slug}: average token count {avg:.0f} outside expected range 100-1000"
            )

    def test_agency_avg_tokens_reasonable(self, db):
        """Agency chunks should average 200-2000 tokens."""
        for slug in ("dir", "edd", "calhr"):
            row = db.execute(
                """SELECT AVG(c.token_count) as avg_tok
                   FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   JOIN sources s ON d.source_id = s.id
                   WHERE s.slug = ? AND c.is_active = 1""",
                (slug,),
            ).fetchone()
            avg = row["avg_tok"]
            assert 200 <= avg <= 2000, (
                f"{slug}: average token count {avg:.0f} outside expected range 200-2000"
            )


# ── 9. Specific content verification ─────────────────────────


class TestSpecificContent:
    """Verify that key statutory sections contain expected substantive content."""

    def test_lab_code_510_overtime(self, db):
        """Labor Code § 510 should mention overtime and eight hours."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'labor_code' AND c.citation LIKE '%§ 510.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "Labor Code § 510 not found"
        content = row["content"].lower()
        assert "eight" in content or "overtime" in content or "hours" in content, (
            f"Lab Code § 510 doesn't mention overtime/hours: {content[:200]}"
        )

    def test_lab_code_1102_5_whistleblower(self, db):
        """Labor Code § 1102.5 should mention retaliation or whistleblower concepts."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'labor_code' AND c.citation LIKE '%§ 1102.5.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "Labor Code § 1102.5 not found"
        content = row["content"].lower()
        assert any(term in content for term in ("retaliat", "disclose", "report", "violation")), (
            f"Lab Code § 1102.5 doesn't contain whistleblower concepts: {content[:200]}"
        )

    def test_gov_code_12940_feha(self, db):
        """Gov Code § 12940 should mention unlawful employment practices."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'gov_code_feha' AND c.citation LIKE '%§ 12940.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "Gov Code § 12940 not found"
        content = row["content"].lower()
        assert any(term in content for term in ("employer", "discriminat", "harass", "unlawful")), (
            f"Gov Code § 12940 doesn't contain FEHA concepts: {content[:200]}"
        )

    def test_bpc_16600_noncompete(self, db):
        """BPC § 16600 should mention restraint of trade / void."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'bus_prof_code' AND c.citation LIKE '%§ 16600.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "BPC § 16600 not found"
        content = row["content"].lower()
        assert any(term in content for term in ("void", "restrain", "lawful profession", "trade")), (
            f"BPC § 16600 doesn't mention non-compete concepts: {content[:200]}"
        )

    def test_bpc_17200_ucl(self, db):
        """BPC § 17200 should define unfair competition."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'bus_prof_code' AND c.citation LIKE '%§ 17200.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "BPC § 17200 not found"
        content = row["content"].lower()
        assert any(term in content for term in ("unfair", "competition", "unlawful", "fraudulent")), (
            f"BPC § 17200 doesn't mention unfair competition: {content[:200]}"
        )

    def test_ccp_425_16_anti_slapp(self, db):
        """CCP § 425.16 should mention SLAPP or free speech / petition."""
        row = db.execute(
            """SELECT c.content FROM chunks c
               JOIN documents d ON c.document_id = d.id
               JOIN sources s ON d.source_id = s.id
               WHERE s.slug = 'ccp' AND c.citation LIKE '%§ 425.16.%'
               AND c.is_active = 1 LIMIT 1""",
        ).fetchone()
        assert row is not None, "CCP § 425.16 not found"
        content = row["content"].lower()
        assert any(term in content for term in ("free speech", "petition", "public participation", "motion to strike", "arising from")), (
            f"CCP § 425.16 doesn't mention anti-SLAPP concepts: {content[:200]}"
        )
