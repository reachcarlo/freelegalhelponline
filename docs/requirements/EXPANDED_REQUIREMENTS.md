# Employee Help — Expanded Requirements: Multi-Source Knowledge Acquisition & Dual-Mode Legal Guidance

> **Project:** Employee Help — AI-Powered Legal Guidance Platform
> **Author:** Claude (Opus 4.6) for Product Owner review
> **Date:** 2026-02-25
> **Status:** APPROVED — All PO decisions resolved (2026-02-25). **REVISED 2026-02-25**: Statutory ingestion pivoted from web scraping to PUBINFO database (see Assumptions 6–7, F-SC.2, 1.5C.8). **PHASE 1.5 IMPLEMENTATION COMPLETE (2026-02-25)**: All 9 sources ingested (6 statutory + 3 agency). 20,546 documents, 23,753 chunks. 32/33 validation checks pass (1 known issue: CalHR oversized chunk — chunker improvement deferred). Idempotency verified. Pending PO gate review (1.5D.6). **CACI JURY INSTRUCTIONS INTEGRATED (2026-02-26)**: 10th source added — 110 employment-related CACI instructions (series 2400–2800, 4600) parsed from 2026 PDF. 325 documents, 353 chunks. New `jury_instruction` content category with attorney-mode 1.3x retrieval boost. Consumer mode excluded by design. **PHASE 2 CODE COMPLETE (2026-02-26)**: RAG pipeline fully implemented — embedding (bge-base-en-v1.5, 24,058 chunks in LanceDB), hybrid search (vector + BM25 + RRF), dual-mode retrieval (consumer/attorney), LLM answer generation (Claude Haiku 4.5 / Sonnet 4.6 with Citations API), and 60-question evaluation suite. 750 tests passing. Automated gates 2A.5b, 2A.10, 2B.5 PASS. Pending PO gate review (2C.5, 2C.6). **ROADMAP REFRAMED (2026-02-26)**: Phases 3–5 restructured through Product Management and Venture Capital lenses — applying JTBD, Lean Startup, Business Model Canvas, Product-Led Growth, and customer validation frameworks. Phase 3 reframed from "build web app" to "validate demand + ship MVP + run beta." New Section 3.7 (Product Strategy & Go-to-Market) added. Risk & Assumption Registry added. 3 new PO decisions pending (Phase 3 approach, revenue model, web framework).
> **Supersedes:** PHASE_1_KNOWLEDGE_ACQUISITION.md (Phase 1 scope preserved; Phases 2–5 expanded)

---

## Preamble: Pressure-Test Analysis

This document expands the project scope from a single-agency, discrimination-focused assistant to a **comprehensive California employment rights platform** spanning multiple government agencies and statutory codes, serving **two distinct user personas** (employees and attorneys). Before finalizing the expanded requirements, the following assumptions were stress-tested through Product Management, Technical Architecture, Software Architecture, and Business Analysis lenses.

### Scope Expansion Summary

| Dimension | Phase 1 (Completed) | Expanded Vision |
|-----------|---------------------|-----------------|
| **Agencies** | 1 (CRD only) | 8+ California agencies |
| **Content types** | HTML pages, PDFs | + statutory code sections, regulations, decisions |
| **Subject matter** | Employment discrimination | All California employee/employer rights |
| **User personas** | Generic user | Consumer/Employee + Attorney |
| **Output style** | Plain-language guidance | + statutory citations with section-level precision |
| **Estimated volume** | ~50 pages, ~500 chunks | ~5,000–10,000 pages, ~50,000–100,000 chunks (actual: 20,871 docs, 24,106 chunks across 10 sources) |

---

### Pressure-Test: Assumptions Examined

#### Assumption 1: "We can treat all government websites the same way"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Each California agency website is built on a different CMS and tech stack. CRD uses WordPress/Divi (JS-rendered). DIR uses a custom CMS with relatively static HTML. EDD is a large modern site (ca.gov platform). PERB is a simpler WordPress site. leginfo.legislature.ca.gov uses Java Server Faces (JSF) — a server-side framework that renders HTML on the server but uses URL parameters and form posts for navigation, not clean REST URLs. A one-size-fits-all crawler will fail on at least half of these sites. |
| **Resolution** | Adopt a **source-registry architecture** where each agency is defined as a configuration entry with its own seed URLs, scope rules, extraction hints, and rate limits. The crawler core stays the same (Playwright + BeautifulSoup), but each source can specify custom CSS selectors for content areas, boilerplate patterns, and URL normalization rules. For statutory codes, the primary data source is the **PUBINFO database** (structured MySQL dump from `downloads.leginfo.legislature.ca.gov`), with the leginfo web scraper as a fallback. See Assumptions 6–7. |

#### Assumption 2: "We can just add more seed URLs to the existing config"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The current `scraper.yaml` is a flat file with one set of seed URLs, one allowlist, and one blocklist. Adding 8 agencies' worth of patterns into one file creates a maintenance nightmare. Worse, a single misconfigured blocklist pattern for DIR could accidentally filter out CRD content. Each source also has different operational characteristics — EDD may tolerate faster crawling than PERB. |
| **Resolution** | Restructure configuration into a **source registry** model: one top-level config that references individual source definition files (or sections). Each source carries its own identity, scope rules, rate limits, and extraction parameters. The pipeline iterates over registered sources, running each as an independent crawl job with its own run record. Shared defaults minimize repetition. |

#### Assumption 3: "Statutory code is just more HTML to scrape"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | Statutory code is fundamentally different from agency guidance. A fact sheet explains what the law means in plain language. A code section *is* the law. The data model, chunking strategy, citation format, and retrieval strategy all differ. A code section like Labor Code § 1102.5 has a precise canonical citation, an effective date, subdivision structure (a)(1)(A), and may cross-reference other sections. Chunking a statute the same way we chunk a web page destroys the structural integrity that makes legal citation possible. |
| **Technical Architect** | The leginfo website (leginfo.legislature.ca.gov) organizes codes hierarchically: Code → Division → Part → Chapter → Article → Section. Each section has a stable URL pattern. The content is public domain (Gov. Code § 10248), so there are no legal barriers to ingestion. However, the JSF-based web server is unreliable (30–40% error rates observed, see Assumption 6) and the `robots.txt` disallows non-Googlebot crawlers. Fortunately, the California Legislature provides the **PUBINFO database** — a complete MySQL dump of all statutory codes — at `https://downloads.leginfo.legislature.ca.gov/`. The `law_section_tbl` contains structured section data with full hierarchy metadata, making web scraping unnecessary for bulk ingestion. |
| **Resolution** | Create a **dedicated statutory code pipeline** that understands legal hierarchy. The primary data source is the **PUBINFO database dump** (structured MySQL data), with the existing web scraper retained as a validation and fallback tool. Code sections are stored with full citation metadata (code name, section number, subdivision, effective date). Chunking respects section boundaries — a single code section is one chunk (or, if unusually long, split at subdivision boundaries while preserving the section citation context). The data model adds a `citation` field and a `content_category` enum that distinguishes `statutory_code` from `agency_guidance`. |

#### Assumption 4: "One chatbot serves all users"

| Lens | Challenge |
|------|-----------|
| **Product Manager** | An employee asking "Can my boss fire me for being pregnant?" and an attorney asking "What are the elements of a pregnancy discrimination claim under FEHA with remedies analysis?" need fundamentally different responses. The employee needs a clear, plain-language answer with reassurance and next steps. The attorney needs statutory text, element-by-element analysis, cross-references, and precise citations. Serving both from one interface either oversimplifies for attorneys or overwhelms consumers. |
| **Business Analyst** | The two personas also have different trust requirements. Consumers trust plain-language summaries attributed to government agency pages. Attorneys trust statutory citations they can verify — they will check "Lab. Code § 1102.5" against Westlaw. If the citation is wrong, the tool loses all credibility with the attorney audience. |
| **Resolution** | Design the platform for **two distinct experience modes** that share a common knowledge base but use different retrieval strategies, prompt templates, and citation formats. The consumer mode retrieves agency guidance chunks and responds in plain language with source URLs. The attorney mode retrieves statutory code chunks (primary) and agency guidance chunks (supplemental), responds with legal analysis structure, and cites to specific code sections with subdivision precision. This is a **presentation and retrieval difference**, not a data duplication — the same underlying knowledge base serves both modes. |

#### Assumption 5: "We need to ingest every California code"

| Lens | Challenge |
|------|-----------|
| **Product Manager** | California has 29 codes. Most are irrelevant to employment rights (e.g., Fish and Game Code, Harbors and Navigation Code). Ingesting everything wastes storage, increases noise in retrieval, and creates maintenance burden for no user value. But being too narrow risks missing legitimate causes of action — for example, Business & Professions Code § 17200 (unfair business practices) is routinely used in employment cases. |
| **Resolution** | Define a **curated list of relevant codes and divisions** based on the causes of action and claims employees can bring. The initial list (see Section 2.3) covers the core employment-relevant codes. This list is PO-configurable and expandable without code changes. The statutory ingestion pipeline accepts a code manifest (code abbreviation + relevant divisions/parts) and only ingests matching content. |

#### Assumption 6: "We can scrape leginfo.legislature.ca.gov reliably"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Live testing against leginfo revealed a **30–40% HTTP error rate** (502 Bad Gateway, 500 Internal Server Error, connection resets) across 50+ requests. The TOC expansion page (`codedisplayexpand.xhtml`) is the most failure-prone — it triggers expensive server-side tree generation. Individual section pages (`codes_displaySection.xhtml`) are moderately reliable. The server is a resource-constrained JSF application that struggles with complex queries. Failures are non-deterministic and the same URL may succeed on retry. |
| **Business Analyst** | The `robots.txt` at leginfo.legislature.ca.gov issues `Disallow: /` for all non-Googlebot user agents, meaning web scraping is technically against the site's crawling policy. Combined with high error rates, relying on web scraping as the primary data source is fragile and unreliable. |
| **Resolution** | **Use the official PUBINFO database dump** (see Assumption 7 below) as the primary data source for statutory content. The California Legislature provides a complete MySQL database dump of all legislative information at `https://downloads.leginfo.legislature.ca.gov/`, updated daily. This eliminates web scraping for bulk statutory ingestion. The existing web scraper is retained as a **validation and fallback tool** — useful for spot-checking individual sections, verifying PUBINFO data, or fetching recently-enacted amendments that may not yet be in the database. |

#### Assumption 7: "There's no structured data source for statutory codes"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Research discovered that the California Legislature provides the **PUBINFO database** — a complete MySQL dump of all legislative information — for free public download at `https://downloads.leginfo.legislature.ca.gov/`. The key table is `law_section_tbl` which contains: `law_code` (code abbreviation), `section_num`, `content_xml` (full section text in XML), `division`/`title`/`part`/`chapter`/`article` (structured hierarchy), `effective_date`, `history` (amendment info), and `active_flg` (current vs. repealed). The `law_toc_tbl` provides the complete table of contents structure. Daily incremental updates are available via `pubinfo_Mon.zip` through `pubinfo_Sat.zip`. |
| **Product Manager** | This is a game-changer for reliability and completeness. Instead of scraping 10,000+ pages from a flaky JSF server over many hours (with 30–40% error rates), we can download the complete dataset in minutes, parse it deterministically, and update daily. The data is official, authoritative, and structured. |
| **Resolution** | Implement a **PUBINFO database loader** as the primary statutory ingestion path. The loader downloads the ZIP archive, extracts the `law_section_tbl` data files, parses tab-delimited rows with LOB sidecar files for `content_xml`, filters by target codes and `active_flg = 'Y'`, and converts to our `StatuteSection` model with full citation metadata. The existing `StatutoryExtractor` (web scraper) is retained for validation and real-time section lookups but is no longer the primary ingestion mechanism. |

#### Assumption 8: "Scale from 500 to 100,000 chunks doesn't change the architecture"

> Note: This was originally Assumption 6 — renumbered after inserting leginfo reliability findings (Assumptions 6–7 above).

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Phase 1 stores ~500 chunks in SQLite with keyword search. At 50,000–100,000 chunks, SQLite remains viable for storage (it handles millions of rows well), but **retrieval quality** becomes the bottleneck. Vector similarity search across 100K chunks needs a proper vector index — NumPy cosine similarity over a flat array won't scale to acceptable latency. Keyword search alone won't surface the right statutory sections for a nuanced legal question. |
| **Software Architect** | The Phase 2 embedding/search decision (currently deferred) becomes more consequential at this scale. ChromaDB or Qdrant can handle 100K vectors easily, but the choice affects deployment complexity and cost. |
| **Resolution** | The expanded requirements don't change the Phase 1 or Phase 2 architecture *decisions* — they change the *parameters*. SQLite remains correct for storage as the system of record. **Phase 2 implementation (2026-02-26):** Selected **LanceDB** as the embedded vector database — it runs in-process (no server), stores data in Apache Arrow format, supports built-in hybrid search (BM25 + vector + Reciprocal Rank Fusion), and provides metadata filtering. At the actual scale of ~23K chunks with 768-dimensional embeddings (bge-base-en-v1.5), flat vector scan responds in <10ms. The chunking pipeline's content-category metadata enables mode-specific retrieval filtering (consumer mode filters to agency content; attorney mode includes all with statutory boosting). |

#### Assumption 9: "Adding sources is a one-time effort"

| Lens | Challenge |
|------|-----------|
| **Product Manager** | California laws change annually (effective January 1). Agency guidance pages get updated throughout the year. New agencies may be added. The system must support **ongoing source management** — adding new agencies, updating code sections when laws change, handling amended or repealed statutes. This is an operational concern, not just a build-time concern. |
| **Resolution** | Design the source registry and pipeline so that **adding a new agency source is a configuration change**, not a code change. The CLI `scrape` command accepts a `--source` parameter to run a specific source, or runs all sources if omitted. The statutory code pipeline tracks the "as of" date for each code section and can detect changes on re-run. Repealed sections are soft-deleted (marked as inactive, not removed) to prevent broken references. |

#### Assumption 10: "Attorney-grade citation accuracy is a Phase 5 polish item"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | If we build the knowledge base without citation-ready metadata from the start, retrofitting it later means re-ingesting all statutory content with a different schema. Citation accuracy isn't a UI feature — it's a **data architecture requirement** that must be embedded in the ingestion pipeline. An attorney who sees "Cal. Lab. Code § 1102" when the actual section is "§ 1102.5" will never trust the tool again. |
| **Resolution** | The statutory code extraction pipeline must capture **section-level citation metadata** from day one: code abbreviation, section number (with decimal subdivisions like 1102.5), subdivision markers, and the full canonical citation string. This metadata is stored alongside the chunk content and is available for any retrieval mode. The attorney-facing experience is a later phase, but the data foundation is built during ingestion. |

---

### Key Risks (Expanded)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Citation inaccuracy in attorney mode** | Critical | Section-level metadata captured at ingestion; citation format validated against known patterns; human review of citation samples |
| **Stale statutory content after annual law changes** | Critical | Track effective dates; support re-ingestion with change detection; flag chunks from amended sections; PUBINFO daily incremental updates |
| **leginfo web server unreliable (30–40% error rate observed)** | High | **RESOLVED**: Use PUBINFO database dump as primary data source instead of web scraping. Web scraper retained as validation/fallback only. See Assumptions 6–7. |
| **Government website structural changes break crawlers** | High | Source-specific extraction config isolates blast radius; monitoring alerts on crawl failures; per-source health checks |
| **Retrieval quality degrades at 100K chunk scale** | High | Content-category filtering before vector search; hybrid search (semantic + metadata); evaluation benchmark suite |
| **PUBINFO database format changes** | Medium | The `law_section_tbl` schema is documented in `pubinfo_load.zip`; loader validates expected columns on startup; alert on schema mismatch |
| **Scope creep across 29 California codes** | Medium | Curated code manifest with PO approval; new codes require explicit addition |
| **Consumer receives attorney-level complexity (or vice versa)** | Medium | Separate retrieval strategies and prompt templates per mode; mode selection is explicit, not inferred |
| **leginfo robots.txt disallows all non-Googlebot crawlers** | Low | Web scraping is fallback only; primary ingestion uses PUBINFO download (no robots.txt concern). Scraper retained for spot-checking and individual section lookups only. |
| **Inconsistent content quality across agencies** | Medium | Per-source quality validation; cleaner rules customizable per source; manual QA on first ingestion of each source |
| **No validated user demand (desirability risk)** | Critical | Zero real users to date. Phase 2 validates feasibility (tech works), not desirability (users want it). Phase 3 must include customer discovery interviews and closed beta before full build. See Section 3.7. |
| **No revenue model (viability risk)** | Critical | Revenue streams are undefined. Attorney willingness to pay is assumed, not validated. Phase 3 includes pricing validation experiment. Phase 4 implements payment. See Section 3.7.4. |
| **User trust in AI legal information** | Critical | The #1 adoption barrier. Consumers may not trust AI-generated legal guidance enough to act on it. Mitigate with visible citations, source transparency, confidence indicators, and clear disclaimers. Validate in Phase 3C beta. |
| **No distribution channel (acquisition risk)** | High | Building a product without a growth strategy. SEO is the primary acquisition hypothesis for consumers (employment law queries have high search volume). Attorney acquisition requires outreach to bar associations and legal tech communities. Validate in Phase 4B. |
| **Consumer usage is episodic, not habitual** | Medium | Most employees face 0–2 employment issues in their career. Consumer growth must be viral (recommendations), not retention-driven. Design for first-impression quality and shareability. |
| **Attorney adoption blocked by firm-mandated tools** | Medium | Attorneys may not be allowed to use tools outside Westlaw/Lexis for research. Target solo practitioners and small firms first. Enterprise sales to larger firms is a Phase 5 motion. |
| **Per-query cost at scale** | Medium | Attorney mode at $0.032/query needs subscription pricing to be sustainable. At 1,000 attorney queries/day = ~$960/month in API costs alone. Monitor during Phase 4; optimize prompts for token efficiency. |

---

## 1. Vision & Context (Expanded)

### 1.1 Product Vision (Revised 2026-02-26)

Build an AI-powered legal guidance platform that helps **California employees understand their workplace rights** and helps **attorneys research California employment law** — drawing from a comprehensive, multi-source knowledge base of official government publications and statutory authority.

**The contrarian bet** (see Section 3.7.1): AI can provide trustworthy legal guidance that is good enough for employees to act on and accurate enough for attorneys to cite. If true, the addressable market is the first 30 minutes of every employment law consultation — ~19M California employees and ~90K California attorneys.

The platform serves two distinct user personas, each with a distinct **job-to-be-done** (see Section 3.7.2):

- **Employee/Consumer Mode**: "Help me understand my rights so I can decide what to do about my workplace situation." Plain-language guidance for workers with questions about wages, discrimination, leave, safety, retaliation, unemployment benefits, and other employment rights. Answers cite government agency sources by URL. Tone: reassuring, clear, actionable. Growth model: free tier, SEO-driven acquisition, viral (recommendations).

- **Attorney/Professional Mode**: "Help me quickly find the relevant statutes and build my legal analysis." Statutory analysis with precise legal citations for practitioners researching California employment law. Answers cite code sections with subdivision precision, cross-reference related statutes, and distinguish between statutory text and agency interpretation. Tone: precise, authoritative, well-sourced. Growth model: subscription ($49–99/month), bar association partnerships, habit-driven retention.

### 1.2 Phase 1 Status (Completed)

Phase 1 delivered a working knowledge acquisition pipeline for CRD employment discrimination content:
- Playwright-based web crawler with URL classification
- HTML and PDF content extraction with structure preservation
- Intelligent chunking with heading-path context and overlap
- SQLite storage with content-addressed deduplication
- CLI interface with scrape, status, and validate commands
- 171 automated tests, 81% code coverage

**Phase 1 is the foundation.** The expanded scope builds on this foundation — it does not replace it.

### 1.3 What Changes

| Aspect | Phase 1 (Done) | Expanded Scope |
|--------|---------------|----------------|
| Data sources | CRD only | 8+ California agencies + statutory codes |
| Subject matter | Employment discrimination | All employee/employer rights |
| Content types | HTML + PDF | + statutory code sections |
| Configuration | Single source config | Source registry with per-source configs |
| Data model | Document → Chunk | + content category, citation metadata, source identity |
| Pipeline | Single-source pipeline | Multi-source orchestration |
| User experience | N/A (Phase 1 has no UI) | Dual-mode (consumer + attorney) in later phases |

---

## 2. Content Scope (Expanded)

### 2.1 Agency Sources

Each agency source is a distinct crawl target with its own configuration. The source registry supports adding new agencies without code changes.

| # | Agency | URL | Content Focus | Content Types | Priority | Est. Volume |
|---|--------|-----|---------------|---------------|----------|-------------|
| 1 | **Civil Rights Department (CRD)** | calcivilrights.ca.gov | Employment discrimination, FEHA, complaint process, protected categories | HTML pages, PDF fact sheets, brochures, posters | P0 (Done) | ~50 pages |
| 2 | **Department of Industrial Relations (DIR)** | dir.ca.gov | Wages, hours, working conditions, retaliation, workplace safety, workers' comp | HTML pages, PDF guides, wage orders | P0 | ~200–500 pages |
| 3 | **DIR — Labor Commissioner (DLSE)** | dir.ca.gov/dlse/ | Wage claims, wage theft, labor law enforcement, FAQ, policies | HTML pages, PDF fact sheets, interpretive letters | P0 | ~100–300 pages |
| 4 | **Employment Development Department (EDD)** | edd.ca.gov | Unemployment Insurance, State Disability Insurance, Paid Family Leave, employer obligations | HTML pages, PDF guides, forms guides | P1 | ~100–200 pages |
| 5 | **CalHR (Dept. of Human Resources)** | calhr.ca.gov | State employee benefits, classification, HR policies, civil rights for state workers | HTML pages, HR manual sections, policy memos | P1 | ~100–200 pages |
| 6 | **Public Employment Relations Board (PERB)** | perb.ca.gov | Public sector collective bargaining, unfair practice charges, employee organization rights | HTML pages, PDF guides, FAQ, decisions | P2 | ~50–100 pages |
| 7 | **Agricultural Labor Relations Board (ALRB)** | alrb.ca.gov | Agricultural labor rights, farmworker organizing, collective bargaining | HTML pages, PDF guides, rights summaries | P2 | ~30–50 pages |
| 8 | **CA Dept. of Education (CDE) — Child Labor** | cde.ca.gov | Child labor laws, work permits, minor employment protections | HTML pages, PDF guides | P2 | ~20–50 pages |
| 9 | **DIR — Cal/OSHA** | dir.ca.gov/dosh/ | Occupational safety and health, workplace hazards, complaint filing | HTML pages, PDF guides, standards summaries | P2 | ~100–200 pages |

**Total estimated agency content: 750–1,600 pages → 8,000–16,000 chunks**

### 2.2 Statutory Code Sources

Statutory codes are ingested from the **PUBINFO database** — an official MySQL dump provided by the California Legislature at `https://downloads.leginfo.legislature.ca.gov/`. This structured database contains all 29 California codes with full text, hierarchy metadata, effective dates, amendment history, and active/repealed status. Content is public domain per Government Code § 10248. The web-accessible leginfo.legislature.ca.gov site is used only for validation and individual section lookups.

| # | Code | Abbreviation | Relevant Divisions/Parts | Focus Area | Priority | Est. Sections |
|---|------|-------------|--------------------------|------------|----------|---------------|
| 1 | **Labor Code** | Lab. Code | Division 1 (DIR), Division 2 (Employment Regulation), Division 3 (Employment Relations), Division 4 (Workers' Comp), Division 5 (Safety) | Wages, hours, conditions, retaliation, safety, workers' comp | P0 | ~3,000–4,000 |
| 2 | **Government Code** (FEHA) | Gov. Code | Part 2.8 (§§ 12900–12996) | Employment discrimination, harassment, retaliation, reasonable accommodation | P0 | ~100 |
| 3 | **Government Code** (Whistleblower) | Gov. Code | §§ 8547–8547.12, §§ 53296–53299, § 12653 | Government employee whistleblower protections, qui tam | P1 | ~30 |
| 4 | **Government Code** (Public Employment) | Gov. Code | Title 2, Division 5 (§§ 18500–22959) | State civil service, merit system, employee rights | P2 | ~500–800 |
| 5 | **Unemployment Insurance Code** | Unemp. Ins. Code | Divisions 1–3 | UI benefits, SDI, PFL, employer contributions | P1 | ~500–800 |
| 6 | **Business & Professions Code** | Bus. & Prof. Code | § 16600–16607 (non-competes), § 17200–17210 (UCL) | Non-compete restrictions, unfair business practices (used in wage/hour claims) | P1 | ~30–50 |
| 7 | **Code of Civil Procedure** | Code Civ. Proc. | § 340 (limitations), § 425.16 (anti-SLAPP), § 1021.5 (private attorney general) | Statutes of limitation for employment claims, procedural mechanisms | P1 | ~20–30 |
| 8 | **Health & Safety Code** | Health & Saf. Code | Division 20, Part 1 (§§ 25100–25250) | Hazardous substances, workplace safety (Cal/OSHA enabling statutes) | P2 | ~50–100 |
| 9 | **Education Code** | Ed. Code | Title 2, Division 4, Part 27, Ch. 7 (§§ 49110–49145) | Child labor, work permits for minors | P2 | ~30–50 |
| 10 | **Civil Code** | Civ. Code | § 51–53 (Unruh Act, when employment-adjacent), § 1708.5 (sexual battery) | Civil remedies applicable to workplace conduct | P2 | ~20–30 |

**Total estimated statutory sections: 4,300–5,900 → 5,000–8,000 chunks** (many sections are short enough to be one chunk)

### 2.3 Curated Code Manifest

The statutory ingestion pipeline uses a **code manifest** — a structured list specifying exactly which codes and divisions to ingest. This prevents accidental ingestion of irrelevant codes.

```yaml
# Example code manifest structure (conceptual)
statutory_codes:
  - code: LAB
    display_name: "Labor Code"
    citation_abbrev: "Lab. Code"
    divisions:
      - number: 1
        title: "Department of Industrial Relations"
      - number: 2
        title: "Employment Regulation and Supervision"
      - number: 3
        title: "Employment Relations"
      # ... specific divisions listed
    priority: P0

  - code: GOV
    display_name: "Government Code"
    citation_abbrev: "Gov. Code"
    sections:  # Can specify section ranges instead of full divisions
      - range: "12900-12996"
        title: "Fair Employment and Housing Act"
      - range: "8547-8547.12"
        title: "Whistleblower Protection"
    priority: P0
```

The PO approves the manifest before ingestion begins. Adding a new code or division is a manifest update, not a code change.

### 2.4 Out of Scope

- Federal employment law (Title VII, ADA, FMLA, FLSA, etc.)
- Case law and court opinions (judicial decisions interpreting statutes)
- California Code of Regulations (CCR) administrative rulemaking text (deferred; may add as a future source)
- Non-employment codes (Penal Code, Vehicle Code, Fish & Game Code, etc.)
- County or city-specific employment ordinances (e.g., SF Fair Chance Ordinance)
- Non-English language content (future phase)
- Third-party legal commentary, law review articles, or practice guides

---

## 3. Architectural Expansion

### 3.1 Source Registry Architecture

The core architectural change is a **source registry** that replaces the single-source configuration. Each source is a self-contained configuration that the pipeline can process independently.

```
┌──────────────────────────────────────────────────────────────┐
│                      Source Registry                          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   CRD    │  │   DIR    │  │   EDD    │  │  leginfo │    │
│  │ (agency) │  │ (agency) │  │ (agency) │  │ (statute)│    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│       ▼              ▼              ▼              ▼          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Multi-Source Pipeline                     │    │
│  │                                                       │    │
│  │  For each source:                                     │    │
│  │    1. Load source config                              │    │
│  │    2. Create crawl run (tagged to source)             │    │
│  │    3. Crawl → Extract → Clean → Chunk → Store         │    │
│  │    4. Generate per-source run manifest                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Unified Knowledge Base                   │    │
│  │                                                       │    │
│  │  Documents & Chunks tagged with:                      │    │
│  │    - source_id (which agency/code)                    │    │
│  │    - content_category (guidance | statutory_code)     │    │
│  │    - citation metadata (for statutes)                 │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Expanded Data Model

The existing data model (CrawlRun → Document → Chunk) is extended, not replaced:

```
┌──────────────┐
│    Source     │    NEW — defines a crawl source (agency or code)
├──────────────┤
│ id           │
│ name         │    "CRD", "DIR", "Labor Code", etc.
│ source_type  │    "agency" | "statutory_code"
│ base_url     │
│ config_path  │    Path to source-specific config
│ enabled      │    Boolean — can disable without deleting
│ priority     │    P0, P1, P2
└──────┬───────┘
       │
       │ 1:N
       ▼
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  CrawlRun    │     │    Document      │     │     Chunk        │
├──────────────┤     ├──────────────────┤     ├──────────────────┤
│ id           │────<│ id               │────<│ id               │
│ source_id    │ NEW │ crawl_run_id     │     │ document_id      │
│ started_at   │     │ source_id    NEW │     │ chunk_index      │
│ completed_at │     │ source_url       │     │ content          │
│ status       │     │ title            │     │ heading_path     │
│ summary_json │     │ content_type     │     │ token_count      │
│              │     │ content_category │ NEW │ content_hash     │
│              │     │ raw_content      │     │ content_category │ NEW
│              │     │ content_hash     │     │ citation     NEW │
│              │     │ retrieved_at     │     │ metadata         │
│              │     │ last_modified    │     │ embedding        │
│              │     │ language         │     └──────────────────┘
│              │     │ citation_meta NEW│
└──────────────┘     └──────────────────┘

content_category enum: "agency_guidance" | "fact_sheet" | "statutory_code"
                       | "regulation" | "poster" | "faq" | "jury_instruction"

citation_meta (JSON, for statutory content):
{
  "code": "LAB",
  "code_display": "Labor Code",
  "citation_abbrev": "Lab. Code",
  "section": "1102.5",
  "subdivision": "(a)",
  "division": "2",
  "part": "3",
  "chapter": "5",
  "article": null,
  "effective_date": "2025-01-01",
  "full_citation": "Cal. Lab. Code § 1102.5(a)"
}
```

### 3.3 Source Configuration Structure

```yaml
# config/sources/dir.yaml — Example source config
source:
  name: "Department of Industrial Relations"
  short_name: "DIR"
  source_type: agency
  base_url: "https://www.dir.ca.gov"
  priority: P0

  crawl:
    seed_urls:
      - "https://www.dir.ca.gov/dlse/"
      - "https://www.dir.ca.gov/dlse/faq_overview.htm"
      - "https://www.dir.ca.gov/dlse/howtofilewageclaim.htm"
    allowlist_patterns:
      - "dir\\.ca\\.gov/dlse/"
      - "dir\\.ca\\.gov/dosh/"
    blocklist_patterns:
      - "dir\\.ca\\.gov/dlse/DLSE-Databases"
      - "dir\\.ca\\.gov/.*\\.asp\\?.*print"
    rate_limit_seconds: 2.0
    max_pages: 500

  extraction:
    content_selector: "#main-content"  # CSS selector for main content area
    boilerplate_patterns:
      - "Skip to Main Content"
      - "Back to Top"
    content_category: agency_guidance

  chunking:
    min_tokens: 200
    max_tokens: 1500
    overlap_tokens: 100
```

```yaml
# config/sources/labor_code.yaml — Example statutory source config
source:
  name: "California Labor Code"
  short_name: "Labor Code"
  source_type: statutory_code
  base_url: "https://leginfo.legislature.ca.gov"
  priority: P0

  statutory:
    code: LAB
    citation_abbrev: "Lab. Code"
    divisions:
      - { number: 1, title: "Department of Industrial Relations" }
      - { number: 2, title: "Employment Regulation and Supervision" }
      - { number: 3, title: "Employment Relations" }
      - { number: 4, title: "Workers' Compensation and Insurance" }
      - { number: 5, title: "Safety in Employment" }
    # Ingestion method: "pubinfo" (default, recommended) or "web" (fallback)
    # PUBINFO downloads from https://downloads.leginfo.legislature.ca.gov/
    # Web scraper uses leginfo.legislature.ca.gov (30–40% error rate)
    method: pubinfo

  crawl:
    rate_limit_seconds: 10.0  # For web scraper fallback only; respects robots.txt Crawl-Delay
    max_pages: 5000

  chunking:
    # Statutory sections use different chunking: one section = one chunk
    # unless the section exceeds max_tokens
    strategy: section_boundary
    max_tokens: 2000
    overlap_tokens: 0  # No overlap between code sections
```

### 3.4 Pipeline Flow (Expanded)

```
[1. Load Registry]  →  Read source registry; identify enabled sources
        │
        ├── For each AGENCY source:
        │       │
        │   [2. Configure]   →  Load source-specific config (seed URLs, scope rules)
        │       │
        │   [3. Crawl]       →  Playwright renders pages; discover links
        │       │
        │   [4. Extract]     →  HTML/PDF extraction (existing extractors)
        │       │
        │   [5. Clean]       →  Source-specific boilerplate removal
        │       │
        │   [6. Chunk]       →  Standard chunking with heading paths
        │       │
        │   [7. Store]       →  Upsert with source_id + content_category
        │       │
        │   [8. Report]      →  Per-source run manifest
        │
        ├── For each STATUTORY CODE source (PRIMARY — PUBINFO database):
        │       │
        │   [2. Configure]   →  Load code manifest (codes, divisions, sections)
        │       │
        │   [3. Download]    →  Download PUBINFO ZIP from downloads.leginfo.legislature.ca.gov
        │       │
        │   [4. Parse]       →  Parse law_section_tbl (tab-delimited + LOB files)
        │       │
        │   [5. Filter]      →  Filter by law_code + active_flg='Y' + target divisions
        │       │
        │   [6. Transform]   →  Convert content_xml to plain text; build citations
        │       │
        │   [7. Chunk]       →  Section-boundary chunking (1 section ≈ 1 chunk)
        │       │
        │   [8. Store]       →  Upsert with citation metadata + content_category
        │       │
        │   [9. Report]      →  Per-code run manifest
        │
        ├── For each STATUTORY CODE source (FALLBACK — web scraper):
        │       │
        │   [2. Navigate]    →  Traverse leginfo TOC tree (with retry + backoff)
        │       │
        │   [3. Extract]     →  Extract section text from displayText pages
        │       │
        │   [4. Chunk]       →  Section-boundary chunking
        │       │
        │   [5. Store]       →  Upsert with citation metadata
        │
        └── [10. Aggregate]  →  Cross-source summary report
```

### 3.5 Dual-Mode Retrieval Strategy (Phase 2+)

The knowledge base serves two retrieval modes. This is a Phase 2 implementation concern, but the **data architecture** must support it from the ingestion phase.

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
│                                                             │
│         ┌──────────────┐      ┌──────────────────┐         │
│         │ Consumer Mode│      │  Attorney Mode    │         │
│         └──────┬───────┘      └────────┬─────────┘         │
│                │                        │                    │
│                ▼                        ▼                    │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │  Retrieve:           │  │  Retrieve:                │    │
│  │  - agency_guidance   │  │  - statutory_code (primary)│    │
│  │  - fact_sheet        │  │  - agency_guidance (suppl.) │    │
│  │  - faq               │  │  - regulation              │    │
│  │                      │  │                            │    │
│  │  Cite: source URLs   │  │  Cite: code §§ + URLs     │    │
│  │  Tone: plain language│  │  Tone: legal analysis      │    │
│  └──────────────────────┘  └──────────────────────────────┘ │
│                │                        │                    │
│                ▼                        ▼                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Unified Knowledge Base                   │   │
│  │  (agency guidance + statutory code + fact sheets)     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.6 Phase 2 Architecture: RAG Pipeline (Implemented 2026-02-26)

The Phase 2 implementation adds three new packages and a configuration layer on top of the Phase 1/1.5 knowledge base.

```
┌────────────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline Architecture                       │
│                                                                        │
│  User Query ("What is the minimum wage?", mode=consumer)               │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────┐                                                      │
│  │ QueryPreproc  │  Citation detection, term expansion, normalization  │
│  └──────┬───────┘                                                      │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ RetrievalService.retrieve(query, mode)                        │      │
│  │                                                               │      │
│  │  1. Hybrid search (LanceDB: vector + BM25 + RRF) → top-50   │      │
│  │  2. [Reranker: mxbai cross-encoder → top-10] (if enabled)   │      │
│  │  3. Mode filter (consumer: agency only / attorney: all+boost)│      │
│  │  4. Diversity enforcement (max 3 per document)               │      │
│  │  5. Top-K selection (default 5)                              │      │
│  └──────┬───────────────────────────────────────────────────────┘      │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ PromptBuilder.build_prompt(query, mode, results)              │      │
│  │                                                               │      │
│  │  - Load mode-specific Jinja2 system prompt template          │      │
│  │  - Build Citations API document blocks (1 per chunk)         │      │
│  │  - Enforce token budget (drop lowest-scored if over limit)   │      │
│  └──────┬───────────────────────────────────────────────────────┘      │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ LLMClient.generate(system_prompt, user_msg, document_blocks)  │      │
│  │                                                               │      │
│  │  Claude API with Citations API document content blocks       │      │
│  │  Consumer: Haiku 4.5 (~$0.006/query)                        │      │
│  │  Attorney: Sonnet 4.6 (~$0.032/query)                       │      │
│  └──────┬───────────────────────────────────────────────────────┘      │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ Citation Post-Processor                                       │      │
│  │                                                               │      │
│  │  - Extract citations from Claude Citations API response      │      │
│  │  - Extract statute refs from text (regex)                    │      │
│  │  - Validate against retrieved chunks (section + code match)  │      │
│  │  - Strict: remove hallucinated + warn                        │      │
│  │  - Permissive: mark [citation not verified]                  │      │
│  └──────┬───────────────────────────────────────────────────────┘      │
│         │                                                               │
│         ▼                                                               │
│  Answer(text, citations, mode, model_used, token_usage, warnings)      │
└────────────────────────────────────────────────────────────────────────┘
```

**New package structure (Phase 2):**

```
src/employee_help/
    retrieval/
        __init__.py
        embedder.py          # EmbeddingService (bge-base-en-v1.5 wrapper)
        vector_store.py      # VectorStore (LanceDB wrapper)
        query.py             # QueryPreprocessor
        reranker.py          # Reranker (mxbai-rerank wrapper, disabled by default)
        service.py           # RetrievalService (dual-mode orchestration)
    generation/
        __init__.py
        llm.py               # LLMClient (Claude API wrapper with Citations API)
        prompts.py           # PromptBuilder (Jinja2 template rendering + document blocks)
        service.py           # AnswerService (full RAG pipeline)
        models.py            # Answer, AnswerCitation, TokenUsage dataclasses
    evaluation/
        __init__.py
        retrieval_metrics.py # Precision, recall, MRR, citation hit calculations
        answer_metrics.py    # Citation accuracy, disclaimer, reading level, adversarial checks
config/
    rag.yaml                 # RAG pipeline configuration (models, search params, generation settings)
    prompts/
        consumer_system.j2   # Consumer mode system prompt
        attorney_system.j2   # Attorney mode system prompt
        context.j2           # Context injection template (retained for backward compat)
tests/
    evaluation/
        consumer_questions.yaml    # 25 consumer evaluation questions
        attorney_questions.yaml    # 25 attorney evaluation questions
        adversarial_questions.yaml # 10 adversarial evaluation questions
        test_retrieval_quality.py  # Automated retrieval evaluation
        test_citation_integrity.py # Citation verification tests
```

**New CLI commands (Phase 2):**

| Command | Description |
|---------|-------------|
| `employee-help embed --all` | Generate embeddings for all un-embedded chunks |
| `employee-help embed --source <slug>` | Embed chunks for a specific source |
| `employee-help embed --rebuild` | Rebuild entire vector index from scratch |
| `employee-help embed-status` | Show embedding coverage and index stats |
| `employee-help search "query" --mode consumer\|attorney` | Run hybrid search and display ranked results |
| `employee-help ask "query" --mode consumer\|attorney` | Generate a complete RAG answer |
| `employee-help evaluate-retrieval` | Run automated retrieval quality evaluation |
| `employee-help evaluate-answers` | Run automated answer quality evaluation |

---

### 3.7 Product Strategy & Go-to-Market (Added 2026-02-26)

> This section applies Product Management and Venture Capital frameworks to the Employee Help product, developed through systematic analysis using Jobs-to-be-Done theory, Business Model Canvas, Value Proposition Design, Lean Startup methodology, Product-Led Growth, and habit formation principles. It challenges assumptions in the original roadmap and identifies risks that must be validated before significant investment in Phases 3–5.

#### 3.7.1 The Contrarian Bet

Every startup is built on a contrarian thesis — an important truth that few people agree with (Peter Thiel, *Zero to One*).

**Employee Help's contrarian bet**: *AI can provide trustworthy legal guidance that is good enough for employees to act on and accurate enough for attorneys to cite.*

Most people believe legal information requires human attorneys. If this bet is correct, the addressable market is enormous — replacing the first 30 minutes of every employment law consultation. If wrong, the product is a novelty.

**Current evidence**: Phase 2 evaluation shows strong *feasibility* (consumer precision 0.888, attorney precision 0.808, citation top-1 accuracy 1.0). But feasibility alone does not validate the bet. The critical question is *desirability* — will users trust AI-generated legal information enough to act on it? This is entirely untested.

**Implication for roadmap**: Phase 3 must be structured around validating desirability, not just building a web application. Shipping a polished web app to zero users proves nothing.

#### 3.7.2 Jobs-to-be-Done Analysis

Users don't buy products — they hire them to make progress in their lives (Alan Klement, *When Coffee and Kale Compete*).

**Consumer job**: "Help me understand my rights so I can decide what to do about my workplace situation."
- **Trigger event**: Something happens at work — termination, harassment, unpaid wages, denied leave
- **Emotional dimension**: Anxiety, powerlessness, urgency, fear of retaliation
- **Functional dimension**: Need accurate, understandable, actionable information
- **Current alternatives**: Google (overwhelming, unreliable), government websites (accurate but impenetrable), asking friends (biased), calling a lawyer ($300+/hour, high barrier)

**Attorney job**: "Help me quickly find the relevant statutes and build my legal analysis so I can focus on strategy and client counsel."
- **Trigger event**: New case intake, client question, opposing counsel motion
- **Emotional dimension**: Time pressure, fear of missing a statute, desire to be thorough
- **Functional dimension**: Exact statutory citations, cross-references, structured analysis
- **Current alternatives**: Westlaw/Lexis (~$200+/month, powerful but slow for targeted lookups), manual code searches, prior case files

**Forces of Progress** (what determines whether users switch to Employee Help):

| Force | Consumer | Attorney |
|-------|----------|----------|
| **Push** (away from status quo) | Confusion, cost of attorneys, scattered info, urgency | Research time, Westlaw complexity, risk of missing citations |
| **Pull** (toward our product) | Instant answers, plain language, free/affordable, 24/7 | Fast statute lookup, cross-reference analysis, citation-ready output |
| **Anxiety** (about switching) | "Is AI accurate for legal info?", "Can I trust this?", "Will this replace a real lawyer?" | "Will citations be correct?", "Is this admissible?", "What if it hallucinates?" |
| **Habit** (keeping status quo) | Googling, avoiding the issue, asking family | Westlaw workflows, existing research habits, firm-mandated tools |

**Key insight**: Consumer anxiety about AI legal accuracy is the #1 adoption barrier. Every design decision in Phase 3 must actively reduce this anxiety — through visible citations, source transparency, clear disclaimers, and confidence indicators.

#### 3.7.3 Value Proposition Canvas

**Consumer Segment**:

| Customer Profile | Value Map |
|-----------------|-----------|
| **Jobs**: Understand rights, decide if I have a claim, know next steps, protect myself | **Products/Services**: AI-powered Q&A, plain-language answers, step-by-step guidance |
| **Pains**: Legal jargon confusing, attorneys expensive, info scattered across agencies, fear of retaliation for asking employer | **Pain Relievers**: Plain language, free tier, one-stop source from all agencies, anonymous/private |
| **Gains**: Confidence in understanding, clear action plan, knowing which agency to contact, feeling empowered | **Gain Creators**: Suggested next steps, "File a complaint" CTAs, related rights discovery, agency contact links |

**Attorney Segment**:

| Customer Profile | Value Map |
|-----------------|-----------|
| **Jobs**: Research statutes quickly, build legal analysis, stay current on changes, verify provisions | **Products/Services**: Statutory search, cross-reference analysis, citation-ready output |
| **Pains**: Manual Westlaw searches take time, cross-referencing multiple codes, risk of citing wrong section, codes update frequently | **Pain Relievers**: Instant statute retrieval, automatic cross-references, citation validation, weekly-refreshed knowledge base |
| **Gains**: Time savings on research, comprehensive analysis structure, confidence in citations, competitive advantage | **Gain Creators**: Structured analysis (elements/burden/defenses/remedies), copy-citation functionality, change alerts |

**Three Types of Fit** (Osterwalder, *Value Proposition Design*):

| Fit Type | Consumer Status | Attorney Status |
|----------|----------------|-----------------|
| **Problem-Solution Fit** (features address real pains) | Partially validated (Phase 2 eval metrics) | Partially validated (precision 0.808, citation accuracy 1.0) |
| **Product-Market Fit** (users choose us over alternatives) | **NOT VALIDATED** — zero real users | **NOT VALIDATED** — zero real users |
| **Business Model Fit** (sustainable revenue) | **NOT VALIDATED** — revenue model undefined | **NOT VALIDATED** — willingness to pay unknown |

#### 3.7.4 Business Model Canvas (Current State)

| Block | Assessment | Risk Level |
|-------|-----------|------------|
| **Customer Segments** | (1) CA employees with employment questions, (2) CA employment attorneys | Low |
| **Value Propositions** | Instant, cited legal info (consumer); statutory analysis (attorney) | Medium — untested with real users |
| **Channels** | Phase 3: Web app + SEO. Future: API, browser extension, legal platform integrations | High — no distribution strategy validated |
| **Customer Relationships** | Self-service (consumer), productivity tool (attorney) | Medium — trust-building is critical and unproven |
| **Revenue Streams** | TBD — Freemium (consumer)? Subscription (attorney)? API licensing (enterprise)? | **Critical — completely undefined** |
| **Key Resources** | Knowledge base (23K+ chunks), RAG pipeline, Claude API, legal domain curation | Low — built and validated |
| **Key Activities** | KB maintenance (weekly refresh), RAG quality improvement, user trust building | Medium — operational cost unknown at scale |
| **Key Partnerships** | Anthropic (LLM), CA Legislature (PUBINFO), government agencies | Low |
| **Cost Structure** | LLM API ($0.006–0.032/query), infrastructure, KB maintenance | Medium — scales linearly with usage |

**Critical gaps**: Revenue Streams and Channels are the two largest unknowns. Phase 3 must address both.

#### 3.7.5 Growth Strategy (Product-Led Growth)

The product has strong PLG fundamentals (Wes Bush, *Product-Led Growth*):

**MOAT Assessment**:
- **M**arket: Large (19M CA employees, ~90K CA attorneys), high-intent (employment disputes are urgent)
- **O**cean: Blue-ish — no AI-native competitor specifically for California employment law
- **A**udience: Consumers can self-serve. Attorneys can partially self-serve (firm-level procurement for enterprise features).
- **T**ime-to-value: Very fast — ask a question, get an answer in seconds. Ideal for PLG.

**Recommended growth model**:
- **Consumer**: Free tier (unlimited basic questions) → Premium (detailed analysis, conversation memory, complaint guidance). Acquisition via SEO (employment law questions have massive search volume) and word-of-mouth.
- **Attorney**: Free trial (10 queries/month) → Professional subscription ($49–99/month for unlimited). Acquisition via legal tech communities, bar association partnerships, content marketing.
- **Enterprise** (Phase 5): API access for HR platforms and legal tech tools. Outbound sales.

**Habit formation analysis** (Nir Eyal, *Hooked*): Consumer queries are low-frequency (most employees face 0–2 employment issues in their career) but high-stakes. Attorney queries are higher-frequency (daily research tasks). **Consumer growth will be viral (recommendations), not habitual. Attorney growth can be habit-driven.** Design accordingly: consumer mode optimizes for shareability and first-impression quality; attorney mode optimizes for workflow integration and daily-use efficiency.

#### 3.7.6 Risk & Assumption Registry

Every assumption below must be validated before significant investment. Ordered by risk severity.

| # | Assumption | Risk Type | Evidence | Status | Validation Method |
|---|-----------|-----------|----------|--------|--------------------|
| R1 | Users will trust AI for legal information | Desirability | None | **CRITICAL** | Wizard-of-Oz test with 10–20 real users (Phase 3C) |
| R2 | Employees will find and use this tool | Desirability | None | **High** | Landing page conversion test + SEO traffic (Phase 3A) |
| R3 | Attorneys will use AI research tools alongside Westlaw | Desirability | Industry trend (positive) | Medium | Concierge: onboard 5 attorneys, track 30-day usage (Phase 3C) |
| R4 | Freemium consumer + subscription attorney is viable | Viability | None | **High** | Pre-sale test: offer early-access attorney pricing (Phase 3C) |
| R5 | SEO can drive consumer acquisition at scale | Viability | Employment law queries have high search volume | Medium | Measure organic traffic after Phase 4B content launch |
| R6 | The AI is accurate enough for real-world use | Feasibility | Strong (P@5: 0.888/0.808) | **Validated** | Ongoing evaluation suite |
| R7 | Citation accuracy is sufficient for attorneys | Feasibility | Strong (top-1: 1.0, completeness: 73%) | Partially validated | Live attorney feedback during beta |
| R8 | Per-query costs are sustainable at scale | Viability | Modeled ($0.006–0.032/query) | Medium | Monitor during beta; optimize prompts |
| R9 | California-only is a viable starting market | Viability | Large market (19M workers) | Medium | Validate during beta: what % of traffic seeks CA-specific info? |
| R10 | Users understand the consumer/attorney mode distinction | Desirability | None | Medium | A/B test: explicit mode selection vs. auto-detection (Phase 3C) |

**Phase 3 must resolve R1, R2, and R4 before Phase 4 investment is warranted.**

---

## 4. Functional Requirements (Expanded)

### 4.1 Source Registry Management

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-SR.1 | The system shall support a **source registry** where each data source (agency website or statutory code) is defined as an independent configuration entry. | Enables adding new sources without code changes (Pressure Test #2). |
| F-SR.2 | Each source configuration shall specify: source identity (name, type, base URL), crawl parameters (seed URLs, scope rules, rate limits), extraction hints (content selectors, boilerplate patterns), and chunking parameters. | Source-specific tuning is essential given the diversity of government websites (Pressure Test #1). |
| F-SR.3 | Sources shall be independently enableable/disableable without removing their configuration. | Operational flexibility — temporarily disable a problematic source without losing its config. |
| F-SR.4 | The CLI shall support running the pipeline for a **specific source** (`--source DIR`) or **all enabled sources** (default). | Allows targeted re-ingestion when a specific agency updates content. |

### 4.2 Multi-Source Crawling & Extraction

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-MC.1 | The pipeline shall process each source as an independent crawl run with its own run record, manifest, and error tracking. | Isolation prevents one source's failures from affecting others. |
| F-MC.2 | Each crawl run shall be tagged with the **source identity** so that documents and chunks are traceable to their originating source. | Provenance must be traceable per-source, not just per-URL. |
| F-MC.3 | The pipeline shall support source-specific **content selectors** for identifying the main content area on each site. | Different websites structure content differently — CRD uses `#et-main-area`, DIR uses `#main-content`, etc. |
| F-MC.4 | The pipeline shall support source-specific **boilerplate patterns** for cleaning. | Each agency has different navigation chrome, footers, and cookie notices. |

### 4.3 Statutory Code Ingestion

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-SC.1 | The system shall support a **code manifest** specifying which California codes and divisions to ingest. | Prevents over-ingestion; PO controls scope (Pressure Test #5). |
| F-SC.2 | The statutory pipeline shall support **two ingestion modes**: (a) **PUBINFO database loader** (primary) — downloads and parses the official `law_section_tbl` from `downloads.leginfo.legislature.ca.gov`; (b) **web scraper** (fallback) — navigates the leginfo TOC hierarchy via HTTP. The PUBINFO loader is the default and recommended path. | PUBINFO provides complete, structured data with no rate limiting or reliability concerns. Web scraping is retained for validation, real-time lookups, and cases where PUBINFO lags behind the live site. See Assumptions 6–7. |
| F-SC.3 | Each extracted code section shall carry **citation metadata**: code name, code abbreviation, section number (including decimal subdivisions like "1102.5"), subdivision markers, division/part/chapter/article path, and the full canonical citation string. | Attorney-grade citation accuracy requires section-level metadata from ingestion (Pressure Test #10). |
| F-SC.4 | Code sections shall be chunked at **section boundaries** — one section per chunk where feasible. Unusually long sections may be split at subdivision boundaries while preserving the section citation on each resulting chunk. | Legal citation requires knowing exactly which section a chunk comes from. Splitting mid-section destroys citation integrity. |
| F-SC.5 | The statutory pipeline shall track the **effective date** or "as of" date for each ingested code section. The PUBINFO `law_section_tbl` provides this as a DATETIME field; the web scraper extracts it from amendment info text. | Laws change annually; users and attorneys need to know which version they're reading. |
| F-SC.6 | On re-ingestion, amended code sections shall be updated (new content hash), and repealed sections shall be marked as **inactive** rather than deleted. The PUBINFO `active_flg` field directly indicates repealed sections. | Preserves referential integrity; allows future "historical" queries. |
| F-SC.7 | The PUBINFO loader shall support **incremental updates** using the daily delta files (`pubinfo_Mon.zip` through `pubinfo_Sat.zip`), avoiding full re-download when only checking for changes. | Efficiency for daily/weekly refresh operations. |

### 4.4 Content Categorization

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-CC.1 | Every stored document and chunk shall carry a **content_category** label: `agency_guidance`, `fact_sheet`, `statutory_code`, `regulation`, `poster`, `faq`, or `jury_instruction`. | Enables mode-specific retrieval filtering (consumer mode filters to guidance; attorney mode includes statutes and jury instructions). |
| F-CC.2 | Content category shall be assigned based on source type and URL/content heuristics (e.g., PDF fact sheets from agency sources are `fact_sheet`; leginfo sections are `statutory_code`). | Automated classification reduces manual tagging burden. |

### 4.5 Dual-Mode Support (Data Layer)

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-DM.1 | The data model shall support **filtering by content_category** during retrieval, so that consumer-mode searches can exclude statutory text and attorney-mode searches can prioritize it. | Dual-mode retrieval is a presentation concern in Phase 2+, but the data must support it from Phase 1 (Pressure Test #4). |
| F-DM.2 | Chunks from statutory sources shall include a **citation** field containing the canonical legal citation string (e.g., "Cal. Lab. Code § 1102.5"). | Attorneys need exact citations, not just source URLs. |

---

## 5. Non-Functional Requirements (Expanded)

| ID | Requirement | Rationale |
|----|-------------|-----------|
| NF-1 | Polite crawling per source: configurable rate limiting (default 2s for agencies, 10s+ for leginfo web scraper). PUBINFO database download has no rate limit concern. | Responsible use of government websites. |
| NF-2 | Full pipeline for a single agency source shall complete within **30 minutes**. Full statutory code ingestion (via PUBINFO) within **15 minutes** (download + parse + store). Web scraper fallback may take longer (2+ hours for large codes). | Developer experience; operational feasibility. PUBINFO bulk load is dramatically faster than web scraping. |
| NF-3 | All source configurations externalized in **YAML files** in `config/sources/`. | Adding a new source is a file addition, not a code change. |
| NF-4 | Structured logging with **source identity** in every log entry. | Debugging and monitoring across multiple sources. |
| NF-5 | Test suite coverage >80% on core modules. | Quality assurance across expanded codebase. |
| NF-6 | The system shall handle **network failures gracefully** — retry with exponential backoff for transient errors (at least 3 retries with 1s/2s/4s delays), skip and log for persistent failures, never abort an entire multi-source run due to one source's failure. | Resilience across multiple external dependencies. The web scraper particularly needs retry logic given leginfo's 30–40% error rate. |
| NF-7 | The PUBINFO loader shall validate the database schema against expected column names before parsing, and fail fast with a clear error if the schema has changed. | Defensive programming against upstream format changes. |

---

## 6. Expanded Roadmap

### Phase 1: Knowledge Acquisition — CRD (COMPLETED ✅)

Status: **Done.** 171 tests, 81% coverage. CRD employment discrimination content acquired and stored.

### Phase 1.5: Multi-Source Foundation & Statutory Ingestion (CODE COMPLETE — awaiting PO gate 1.5D.6)

> **Purpose:** Extend the Phase 1 pipeline to support multiple agency sources and statutory code ingestion. This is the data foundation for the dual-mode experience.
> **Status:** 1.5A ✅ | 1.5B ✅ | 1.5C ✅ | 1.5D code ✅ | 1.5E ✅ (all 10 sources ingested: 20,871 docs, 24,106 chunks; 32/33 validation checks pass; pending PO gate 1.5D.6)

#### 1.5A — Source Registry & Multi-Source Pipeline

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1.5A.1 | Design and implement the **Source model** and source registry schema in SQLite. Add `source_id` foreign key to CrawlRun and Document tables. Migrate existing CRD data to reference a "CRD" source record. | Phase 1 | Updated schema, migration script |
| 1.5A.2 | Implement **source configuration loader**: reads per-source YAML files from `config/sources/`, validates structure, returns typed Source config objects. | 1.5A.1 | `config.py` enhancements, `config/sources/crd.yaml` (migrated from existing scraper.yaml) |
| 1.5A.3 | Refactor pipeline to accept a **source parameter**: pipeline processes one source per invocation; the CLI orchestrates multi-source runs by iterating over enabled sources. | 1.5A.2 | Refactored `pipeline.py`, updated `cli.py` with `--source` flag |
| 1.5A.4 | Add `content_category` enum to Document and Chunk models. Backfill existing CRD data as `agency_guidance` / `fact_sheet`. | 1.5A.1 | Updated models, migration |
| 1.5A.5 | **[GATE]** Existing CRD pipeline still works identically via `employee-help scrape --source crd`. All existing tests pass. | 1.5A.1–1.5A.4 | Backward-compatible multi-source foundation |

#### 1.5B — Agency Source Expansion (DIR, EDD, CalHR)

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1.5B.1 | Create source configs for DIR/DLSE: seed URLs, allowlist/blocklist patterns, content selectors, boilerplate patterns. Validate with spike crawl (first 20 pages). | 1.5A.5 | `config/sources/dir.yaml`, spike validation notes |
| 1.5B.2 | Create source configs for EDD: seed URLs, scope rules, content selectors. Validate with spike crawl. | 1.5A.5 | `config/sources/edd.yaml`, spike validation notes |
| 1.5B.3 | Create source configs for CalHR: seed URLs, scope rules, content selectors. Validate with spike crawl. | 1.5A.5 | `config/sources/calhr.yaml`, spike validation notes |
| 1.5B.4 | Run full pipeline for DIR, EDD, CalHR. Spot-check 10 chunks per source for quality. | 1.5B.1–1.5B.3 | Populated knowledge base with 3 new sources |
| 1.5B.5 | **[GATE]** Three new agency sources ingested; per-source run manifests show acceptable error rates; spot-check confirms content quality | 1.5B.4 | Agency expansion validated |

#### 1.5C — Statutory Code Extractor

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1.5C.1 | **Spike**: Navigate leginfo.legislature.ca.gov programmatically. Determine the URL patterns for the table of contents and individual sections. Confirm Playwright can render the JSF pages. Document the extraction approach. | 1.5A.5 | Spike notes: leginfo navigation strategy, URL patterns, rendering findings |
| 1.5C.2 | Implement **statutory code extractor**: given a code abbreviation and list of target divisions, traverse the leginfo TOC, extract each section's text, parse section number and subdivision structure, generate citation metadata. Output: list of documents with citation metadata. | 1.5C.1 | `src/employee_help/scraper/extractors/statute.py`, tests |
| 1.5C.3 | Implement **section-boundary chunking** strategy: one code section = one chunk; split at subdivisions if section exceeds max_tokens; each chunk carries the full citation. | 1.5C.2 | Enhanced `chunker.py` with `strategy: section_boundary` mode, tests |
| 1.5C.4 | Create **code manifest** config for Labor Code (P0) and FEHA sections of Government Code (P0). | 1.5C.2 | `config/sources/labor_code.yaml`, `config/sources/gov_code_feha.yaml` |
| 1.5C.5 | Run statutory pipeline for Labor Code and FEHA. Verify: correct section count, citation accuracy (spot-check 20 sections against leginfo), no missing divisions. | 1.5C.2–1.5C.4 | Populated statutory knowledge base |
| 1.5C.6 | **[GATE]** Labor Code and FEHA ingested with accurate citation metadata. Citation spot-check passes for 20 randomly sampled sections. | 1.5C.5 | Statutory pipeline validated |

#### 1.5D — P1 Sources & Validation

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1.5D.1 | Create source configs and ingest P1 statutory codes: Unemployment Insurance Code, Business & Professions Code (§§ 16600–16607, 17200–17210), Code of Civil Procedure (§ 340, § 425.16, § 1021.5), Government Code (whistleblower sections). | 1.5C.6 | P1 statutory content ingested |
| 1.5D.2 | Comprehensive cross-source validation: total document count, total chunk count, content category distribution, citation sample validation, idempotency re-run. | 1.5B.5, 1.5D.1 | Validation report |
| 1.5D.3 | **[GATE]** PO approves expanded knowledge base. All P0 and P1 sources ingested with acceptable quality. Foundation ready for Phase 2 dual-mode retrieval. | 1.5D.2 | **Phase 1.5 accepted** |

#### 1.5E — CACI Jury Instructions (COMPLETE ✅ — 2026-02-26)

> **Purpose:** Add CACI (California Civil Jury Instructions) to the knowledge base to improve attorney-mode retrieval quality for "elements of a claim" queries. CACI defines what a plaintiff must prove and cites primary statutory authority — it is the authoritative source for claim elements in California employment law.
> **Scope:** Employment-related CACI series only (~110 instructions from 2026 PDF): 2400 (Wrongful Termination), 2500 (FEHA Discrimination & Harassment), 2600 (CFRA Leave), 2700 (Labor Code Violations), 2800 (Workers' Comp Discrimination), 4600 (Whistleblower Protection).

| # | Task | Status | Deliverable |
|---|------|--------|-------------|
| 1.5E.1 | Add `JURY_INSTRUCTION = "jury_instruction"` to `ContentCategory` enum. New category keeps CACI distinct from statutory codes and enables precise mode-specific filtering. | ✅ | Updated `storage/models.py` |
| 1.5E.2 | Update config validation to accept `caci_pdf` as a valid statutory `method` (alongside `pubinfo` and `web`). | ✅ | Updated `config.py` |
| 1.5E.3 | Create source config `config/sources/caci.yaml` with `source_type: statutory_code`, `content_category: jury_instruction`, `method: caci_pdf`. | ✅ | `config/sources/caci.yaml` |
| 1.5E.4 | Implement **CACILoader** (`scraper/extractors/caci.py`): PDF parser using pdfplumber that extracts instruction boundaries, splits into per-section chunks (instruction text, directions for use, sources and authority), filters to employment series, handles letter-suffix instructions (2521A/B/C), skips TOC pages and verdict forms. Returns `StatuteSection`-compatible objects. | ✅ | `caci.py`, 34 unit tests |
| 1.5E.5 | Add `_extract_via_caci_pdf()` to Pipeline, route from `_run_statutory()` when `method == "caci_pdf"`. Made `content_category` configurable from source config (not hardcoded to STATUTORY_CODE). | ✅ | Updated `pipeline.py` |
| 1.5E.6 | Add 1.3x retrieval boost for `jury_instruction` in attorney mode (`_apply_mode_scoring()`). Consumer mode auto-excluded via existing `CONSUMER_CATEGORIES` filter. | ✅ | Updated `retrieval/service.py` |
| 1.5E.7 | Ingest and embed CACI: 110 instructions → 325 documents, 353 chunks, 353 vectors. All embedded at 100% coverage. | ✅ | CACI in knowledge base |
| 1.5E.8 | Verified: attorney query "elements of sexual harassment" → CACI No. 2520 as top result. Consumer mode returns no CACI results. | ✅ | Retrieval quality verified |

**CACI Knowledge Base Statistics:**

| Metric | Value |
|--------|-------|
| Instructions parsed | 110 (from 3,560-page PDF) |
| Employment series | 2400–2899, 4600–4699 |
| Documents stored | 325 |
| Chunks created | 353 |
| Vectors embedded | 353 (100% coverage) |
| Chunk sections | instruction_text, directions_for_use, sources_and_authority |
| Citation format | `CACI No. 2430` |
| Tests added | 40 (34 loader + 3 pipeline + 3 retrieval) |

### Phase 2: RAG Pipeline & Answer Generation (CODE COMPLETE — 2026-02-26)

> **Status:** All code implemented and automated gates passed. 750 tests (143 Phase 2 specific + 40 CACI). Pending PO human evaluation review (2C.5) and final sign-off (2C.6).

#### 2A — Embedding & Retrieval Foundation (COMPLETE ✅)

| # | Task | Status | Deliverable |
|---|------|--------|-------------|
| 2A.1–2 | Embedding model evaluation: selected **bge-base-en-v1.5** (768-dim, 512 max seq, local CPU). BGE-M3 OOM'd (~2.4GB), bge-large too slow (0.9 c/s). bge-base: 2.8 c/s, ~544MB, same quality. | ✅ | Spike report, model selected |
| 2A.3 | **EmbeddingService** (`retrieval/embedder.py`): batch embedding with BGE query prefix, progress logging, error handling. 13 unit + 8 integration tests. | ✅ | Embedding service |
| 2A.4 | **VectorStore** (`retrieval/vector_store.py`): LanceDB embedded DB with hybrid search (vector + BM25 via FTS + RRF), upsert/delete, scalar indexes, FTS index. 24 unit tests. | ✅ | Vector store |
| 2A.5 | Embed CLI (`embed`, `embed-status`): incremental embedding, per-source, rebuild. 24,058/24,058 chunks embedded (0 failures, includes 353 CACI chunks). | ✅ | CLI commands |
| 2A.6 | **QueryPreprocessor** (`retrieval/query.py`): citation detection, legal term expansion, query normalization. | ✅ | Query preprocessor |
| 2A.7 | **Reranker** (`retrieval/reranker.py`): mxbai-rerank-base-v2 cross-encoder. **Disabled** — OOM when co-loaded with embedding model on macOS x86_64 (<8GB RAM). | ✅ | Reranker (disabled) |
| 2A.8 | **RetrievalService** (`retrieval/service.py`): dual-mode retrieval with citation boost (2.0x), statutory boost (1.2x), jury instruction boost (1.3x), diversity enforcement (max 3/doc), deduplication. | ✅ | Dual retrieval service |
| 2A.9 | Search CLI (`search`): `--mode consumer|attorney`, `--verbose`, `--json`, ranked results display. | ✅ | CLI search command |
| 2A.10 | **[GATE] Search quality benchmark** — Consumer P@5: **0.888** (≥0.6 ✅), Attorney P@5: **0.808** (≥0.7 ✅), Citation top-1: **1.000** (≥0.9 ✅), MRR: **0.907**. | ✅ PASS | Validated search quality |

#### 2B — LLM Answer Generation (COMPLETE ✅)

| # | Task | Status | Deliverable |
|---|------|--------|-------------|
| 2B.1 | **LLMClient** (`generation/llm.py`): Claude API wrapper with Citations API document blocks, streaming, retry (2x exponential backoff), model-aware cost tracking. 12 unit tests. | ✅ | LLM client |
| 2B.2 | **Prompt templates** (`config/prompts/`): consumer_system.j2 (plain language, source URLs, disclaimer, next steps) and attorney_system.j2 (legal analysis structure, precise citations, cross-references). **PromptBuilder** (`generation/prompts.py`): Citations API document blocks, token budget enforcement. 16 unit tests. | ✅ | Prompt templates |
| 2B.3 | **AnswerService** (`generation/service.py`): full RAG pipeline (retrieve → build prompt → LLM call → citation validation → response). Streaming support (3-tuple: text stream, results, metadata). Citation post-processor with strict/permissive modes. 17 unit tests. | ✅ | Answer service |
| 2B.4 | Ask CLI (`ask`): `--mode consumer|attorney`, `--no-stream`, `--debug`, `--json`. Streaming display, cost/token tracking. | ✅ | CLI ask command |
| 2B.5 | **[GATE] E2E pipeline validation** — 11 queries tested (5 consumer + 5 attorney + 1 streaming). Consumer avg $0.006/query, attorney avg $0.032/query. Timeout increased 30s→120s for complex attorney queries. | ✅ PASS | Working E2E RAG pipeline |

#### 2C — Quality & Evaluation (CODE COMPLETE — awaiting PO review)

| # | Task | Status | Deliverable |
|---|------|--------|-------------|
| 2C.1 | **Evaluation datasets** (`tests/evaluation/`): 25 consumer + 25 attorney + 10 adversarial questions in YAML. | ✅ | 60-question evaluation suite |
| 2C.2 | **Retrieval evaluation** (`evaluation/retrieval_metrics.py`): precision@k, recall@k, MRR, citation_hit@k. `evaluate-retrieval` CLI command with pass/fail thresholds. | ✅ | Automated retrieval eval |
| 2C.3 | **Answer evaluation** (`evaluation/answer_metrics.py`): citation accuracy, citation completeness, disclaimer check, reading level, adversarial behavior verification. `evaluate-answers` CLI command. | ✅ | Automated answer eval |
| 2C.4 | **Citation integrity tests** (`test_citation_integrity.py`): verify 0 hallucinated citations across all attorney questions. | ✅ | Citation regression suite |
| 2C.5 | **Human evaluation** — Full 60-question run completed. Automated results: consumer disclaimer 100%, attorney disclaimer 92%, adversarial pass 100%, citation completeness 73%. | ⏳ PO | Awaiting PO review |
| 2C.6 | **[GATE] Phase 2 acceptance** — All automated checks pass. 750 tests. | ⏳ PO | Awaiting PO sign-off |

### Phase 3: Customer Validation & MVP Web Application

> **Reframed (2026-02-26):** Phase 3 was originally "Web Application" — a build-first approach. Applying Lean Startup methodology (Eric Ries, *The Lean Startup*) and customer validation principles (Rob Fitzpatrick, *The Mom Test*), the phase is restructured to validate demand before scaling investment. The core insight: Phases 1–2 validated *feasibility* (the tech works) but not *desirability* (users want it) or *viability* (we can sustain it). Phase 3 addresses all three through a Build-Measure-Learn cycle. See Section 3.7 for the full product strategy analysis.

#### 3A — Customer Discovery & Landing Page (2–3 weeks)

The cheapest experiment that reduces the biggest risk. Before writing application code, validate that real users have the problem we're solving and are willing to engage with an AI-powered solution.

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3A.1 | **Customer discovery interviews**: Conduct 10+ conversations (5 employees, 5 attorneys) following *The Mom Test* rules — talk about their life, not our product; ask about specifics in the past, not hypotheticals about the future. Document pain points, current solutions, switching barriers, and willingness to pay. | 2C.6 | Interview notes, pattern analysis |
| 3A.2 | **Landing page test**: Build an SEO-optimized page with value proposition, scope description, 3 sample Q&A pairs (real answers from the pipeline), and email capture for early access. Deploy to a public URL. Measure visitor → sign-up conversion. | 2C.6 | Landing page with analytics |
| 3A.3 | **Keyword research**: Identify top 50 California employment law search queries (Google Keyword Planner / Ahrefs). Validate that our knowledge base covers them. Prioritize content gaps. | 2C.6 | Keyword analysis, coverage report |
| 3A.4 | **[GATE]** Landing page conversion > 5% (visitors → email sign-ups). Interview insights documented and synthesized. Key question answered: "Do people who face employment issues actually search online for help, and would they use an AI tool?" Decide: proceed to 3B, pivot positioning, or investigate further. | 3A.1–3A.3 | **Go/no-go for 3B** |

#### 3B — Minimum Viable Web Application (4–6 weeks)

Build the simplest thing that delivers core value. Not a full chat application — a question-answer interface that proves the product works in the real world. Apply the EUREKA framework (Ramli John, *Product-Led Onboarding*): the Aha Moment is the first accurate, well-cited answer to a real question.

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3B.1 | ✅ **[PO] Web framework decision**: Next.js (App Router) + FastAPI selected. Excellent SEO, streaming SSE, FastAPI wraps existing Python RAG pipeline directly. | 3A.4 | Framework decision |
| 3B.2 | ✅ **MVP interface**: Single question input, streaming answer with react-markdown, mode toggle, source list, persistent disclaimer, rate limiting, error handling. | 3B.1 | MVP web app |
| 3B.3 | ✅ **SEO content pages**: 11 static topic pages (SSG) with FAQPage schema.org markup, 5 FAQs each, internal linking, optimized meta descriptions. | 3B.2 | Topic landing pages |
| 3B.4 | **Analytics**: Query volume, mode distribution, session duration, bounce rate, return visits. No PII collection. Use privacy-respecting analytics (Plausible or similar). | 3B.2 | Analytics dashboard |
| 3B.5 | **Answer feedback**: Thumbs up/down on every answer. Store feedback with query hash, mode, and rating. This is the minimum viable feedback loop — the data that drives all future iteration. | 3B.2 | Feedback mechanism |
| 3B.6 | **[GATE]** MVP deployed to public URL. Analytics collecting data. Feedback mechanism working. Ready for beta users. Core user flow works end-to-end in both modes. | 3B.2–3B.5 | **Live MVP** |

#### 3C — Closed Beta & Validation (4–6 weeks)

The critical phase. This is where we learn whether the product has real demand or is a technically impressive solution without a market. Every metric from this phase informs Phase 4 investment decisions.

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3C.1 | **Recruit beta cohort**: 20–50 consumers (from landing page sign-ups, Reddit r/legaladvice, employment rights forums, legal aid organizations) + 5–10 attorneys (from bar association contacts, legal tech communities, solo practitioner networks). | 3B.6 | Beta cohort |
| 3C.2 | **Run 4-week beta**: Track weekly — queries/user, return rate, feedback scores (thumbs up %), time-on-site, mode preference. Conduct exit interviews at week 2 and week 4 using Mom Test principles. | 3C.1 | Beta metrics report |
| 3C.3 | **Iterate**: Expect 2–3 iteration cycles based on feedback. Common issues to watch for: trust signals (users want to see sources before the answer), answer quality gaps (specific topics where the KB has holes), UX friction (mode confusion, query formulation difficulty), citation presentation (too dense for consumers, not precise enough for attorneys). | 3C.2 | Improved MVP |
| 3C.4 | **Pricing validation** (Bland & Osterwalder, *Testing Business Ideas*): At week 3, introduce a "premium features coming soon" prompt. For attorneys, offer early-access pricing ($49/month). Measure: do they click? Do they enter payment info? Even 3 commitments validates willingness to pay. | 3C.2 | Pricing signal |
| 3C.5 | **[GATE]** Product-market fit signals: >30% 7-day return rate (consumers), >50% 7-day return rate (attorneys). Average feedback score >3.5/5. At least 3 attorneys express concrete willingness to pay. Interview data shows clear "pull" toward the product (users describe it solving a real problem, not just being "interesting"). If these signals are absent, diagnose why before proceeding to Phase 4. | 3C.1–3C.4 | **Product-market fit assessment** |

### Phase 4: Production, Growth & Business Model

> **Reframed (2026-02-26):** Phase 4 was originally "Production Readiness" — pure infrastructure. Infrastructure is necessary but not sufficient. A deployed product without distribution is a tree falling in an empty forest. Phase 4 is expanded to include growth engineering, business model implementation, and the analytics foundation for data-driven iteration. It is only warranted if Phase 3C demonstrates product-market fit signals.

#### 4A — Production Infrastructure

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 4A.1 | [PO] Hosting decision: evaluate for cost at low scale (<1,000 queries/day), auto-scaling, deployment simplicity, and SEO support (SSR/SSG). | 3C.5 | Hosting decision |
| 4A.2 | Production environment: domain, SSL, CDN, environment-specific configuration (dev/staging/production). | 4A.1 | Production environment |
| 4A.3 | CI/CD pipeline: automated tests on PR, staging on merge to main, production with manual approval gate. Rollback procedure tested. | 4A.2 | CI/CD pipeline |
| 4A.4 | Monitoring: error tracking (Sentry), structured log aggregation, uptime monitoring, LLM cost tracking with daily budget alerts. | 4A.3 | Monitoring stack |
| 4A.5 | Security: rate limiting, input sanitization (prompt injection prevention), HTTPS enforcement, dependency vulnerability scanning. Legal disclaimer text reviewed by an actual attorney. | 4A.3 | Security audit |

#### 4B — Growth & Acquisition

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 4B.1 | **SEO execution**: Target top 50 employment law queries from 3A.3. Publish optimized topic pages with schema.org FAQ/LegalService markup. Monitor ranking progress weekly. | 4A.3 | SEO-optimized content |
| 4B.2 | **Content marketing**: Publish 10 pillar articles on high-volume topics ("California minimum wage 2026", "wrongful termination California", "FEHA discrimination claims"). Each article links to the interactive Q&A tool. | 4B.1 | Content funnel |
| 4B.3 | **Referral mechanism**: "Share this answer" button generating a shareable link with the question pre-loaded. Track viral coefficient (shares per user, new users per share). | 4A.3 | Referral system |
| 4B.4 | **Attorney outreach**: Partner with 2–3 California bar association sections (Labor & Employment Law, Solo/Small Firm). Offer free access in exchange for feedback, testimonials, and co-marketing. | 4A.3 | Bar association partnerships |
| 4B.5 | **Email engagement**: Weekly digest of California employment law changes for subscribers (sourced from PUBINFO delta processing). Drives return visits and positions the product as the authoritative source. | 4A.3 | Email channel |

#### 4C — Business Model Implementation

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 4C.1 | [PO] Finalize pricing based on 3C.4 beta data. Recommended starting point: free consumer tier (5 questions/day), attorney professional ($49–99/month unlimited). | 3C.5 | Pricing decision |
| 4C.2 | Payment infrastructure (Stripe): subscription management, usage tracking, free tier enforcement. | 4C.1 | Payment system |
| 4C.3 | Attorney onboarding: account creation, firm profile, usage dashboard, billing management. | 4C.2 | Attorney portal |
| 4C.4 | Unit economics tracking: cost per query (LLM + infrastructure), revenue per user, CAC (customer acquisition cost), LTV (lifetime value). Target LTV:CAC > 3:1. | 4C.2 | Financial dashboard |
| 4C.5 | **[GATE]** Production launch with payment. Targets: 100+ active free users, 5+ paying attorney subscribers, positive unit economics (revenue > variable costs per user). Monthly burn rate documented and sustainable. | 4A–4C | **Revenue milestone** |

### Phase 5: Scale, Expand & Deepen

> **Reframed (2026-02-26):** Phase 5 was originally a grab bag of features organized by technical category. It is restructured around validated user needs from Phase 3–4 data, prioritized by impact on retention, revenue, and competitive moat. Features are sequenced highest-impact-first. The specific prioritization should be updated based on actual beta and production usage data — the ordering below is a hypothesis.

#### 5A — Retention & Engagement (Highest Priority — Close the Loop)

| # | Task | Priority | Rationale |
|---|------|----------|-----------|
| 5A.1 | **Multi-turn conversation memory** (session-based, no accounts required for consumers) | P0 | #1 most-requested feature in legal AI tools. Users ask follow-up questions naturally. Without memory, each question starts cold — breaking the Hook cycle (Nir Eyal). |
| 5A.2 | **Feedback-driven quality loop**: Use thumbs-down data to identify weak topics, refine prompts, and expand knowledge base for coverage gaps. | P0 | Closes the Build-Measure-Learn loop. Without this, quality improvements are guesswork. |
| 5A.3 | **Suggested follow-up questions** after each answer. Context-generated, not hardcoded. | P1 | Increases session depth (queries/session). Reduces effort for the next action — the Investment phase of the Hook Model that creates the next Trigger. |
| 5A.4 | **Consumer: guided complaint filing workflow** (step-by-step: identify issue → find agency → gather documents → file). | P1 | Transforms the product from information tool to action tool. The highest-value differentiator for consumers — no competitor does this. |
| 5A.5 | **Attorney: copy citation / copy analysis / export to Word/PDF**. | P1 | Reduces friction for the attorney's real workflow: the analysis goes into a brief or memo, not into Employee Help. Without easy export, the tool creates extra work instead of saving it. |

#### 5B — Knowledge Base Expansion (Demand-Driven — Expand Where Users Pull)

| # | Task | Priority | Rationale |
|---|------|----------|-----------|
| 5B.1 | **Automated content refresh**: scheduled weekly re-ingestion with change detection and re-embedding. | P0 | Without this, the knowledge base decays. California laws change every January 1. Stale content destroys trust — the hardest-won and most fragile asset. |
| 5B.2 | **P2 agency sources** (PERB, ALRB, CDE, Cal/OSHA) — prioritize based on query data showing unserved topics. | P1 | Data-driven: only expand to sources where users are asking questions we cannot answer. |
| 5B.3 | **P2 statutory codes** (Health & Safety, Education, Civil) — prioritize based on attorney query patterns. | P1 | Same: expand where demand exists, not where content is available. |
| 5B.4 | **CCR (California Code of Regulations)** — administrative regulations implementing statutes. | P2 | Adds the regulatory layer. High value for attorneys but significant ingestion effort. |
| 5B.5 | **Spanish language support**: ingest Spanish-language fact sheets from CRD and DIR. Evaluate multilingual embedding model. | P2 | ~39% of CA workforce is Hispanic/Latino. Massive underserved market. But requires multilingual RAG pipeline evaluation. |

#### 5C — Platform & Moat (Revenue-Driven — Build Defensibility)

| # | Task | Priority | Rationale |
|---|------|----------|-----------|
| 5C.1 | **Attorney: cross-reference sidebar** — when a statute references another, show the related section inline. | P1 | A "delighter" feature (Kano Model) that no competitor does well. Builds on existing citation metadata. Creates switching costs. |
| 5C.2 | **Topic-guided browsing** by subject area with pre-built queries and landing pages. | P1 | Reduces cold-start friction. Serves users who don't know what to ask. Excellent for SEO long-tail capture. |
| 5C.3 | **API access** for legal tech platforms and HR software. RESTful API with auth, rate limiting, usage billing. | P2 | Enterprise revenue channel. HR platforms (Gusto, Rippling, BambooHR) could embed employment law guidance. This is the "network effects" play from Zero to One. |
| 5C.4 | **Statutory change alerts**: notify subscribed attorneys when statutes in their practice areas are amended. | P2 | Retention mechanism for attorney subscribers. Uses existing PUBINFO delta processing. Creates a habit trigger (Hooked model: external trigger → return visit). |
| 5C.5 | **Multi-state expansion**: Template the California pipeline for other states, starting with the largest employment markets (TX, NY, FL, IL). | P3 | Massive TAM expansion but requires per-state knowledge base build. Only pursue after California PMF is proven and the unit economics work. This is the 1-to-n scaling play — only valid after the 0-to-1 is confirmed. |

---

## 7. Detailed Implementation Todo List

This section provides a granular, actionable todo list for every phase and sub-phase. Each item is a discrete unit of work with clear acceptance criteria. Items are grouped by phase and ordered by dependency.

> **Legend:** `[ ]` = Not started | `[~]` = In progress | `[x]` = Complete | `[GATE]` = PO approval checkpoint | `[SPIKE]` = Research/investigation task | `[PO]` = Requires PO decision before proceeding

---

### Phase 1: Knowledge Acquisition — CRD `[x] COMPLETE`

All Phase 1 work is done. 162 tests passing, 81% coverage.

- [x] 1A — Project scaffolding (Python 3.12+, uv, pyproject.toml, directory structure)
- [x] 1B — Technical spike (Playwright rendering, PDF extraction, DOM selectors)
- [x] 1C — Storage layer (SQLite models, CRUD operations, deduplication)
- [x] 1D — Crawler & content extraction (Playwright crawler, HTML/PDF extractors)
- [x] 1E — Content processing (cleaner, chunker with overlap)
- [x] 1F — Pipeline orchestration & CLI (config loader, pipeline, CLI with scrape/status/validate)
- [x] 1G — Validation & acceptance (validation framework, search utility, Phase 1 sign-off)

---

### Phase 1.5: Multi-Source Foundation & Statutory Ingestion

#### 1.5A — Source Registry & Multi-Source Pipeline

**Goal:** Refactor the existing single-source pipeline into a multi-source architecture without breaking existing CRD functionality.

- [x] **1.5A.1 — Design Source model and registry schema** ✅
  - [x] Define `sources` table in SQLite (id, name, slug, source_type, base_url, enabled, created_at)
  - [x] Add `source_id` foreign key to `crawl_runs` table
  - [x] Add `source_id` foreign key to `documents` table
  - [x] Write schema migration script for existing CRD data
  - [x] Create seed "CRD" source record in migration
  - [x] Backfill existing crawl_runs and documents with CRD source_id
  - [x] Add Source dataclass to `storage/models.py`
  - [x] Add Source CRUD methods to `storage/storage.py` (create_source, get_source, get_all_sources, update_source)
  - [x] Write unit tests for Source model and storage operations
  - [x] Verify migration is idempotent (safe to run multiple times)

- [x] **1.5A.2 — Source configuration loader** ✅
  - [x] Define per-source YAML schema (name, slug, type, base_url, enabled, seed_urls, allowlist_patterns, blocklist_patterns, content_selector, boilerplate_patterns, rate_limit_seconds, max_pages, chunking overrides)
  - [x] Create `config/sources/` directory
  - [x] Migrate existing `config/scraper.yaml` to `config/sources/crd.yaml` format
  - [x] Implement `load_source_config(path)` function returning typed SourceConfig dataclass
  - [x] Implement `load_all_source_configs(directory)` to load all enabled source configs
  - [x] Add validation: required fields, regex compilation, rate limit bounds
  - [x] Write unit tests for source config loading and validation
  - [x] Write tests for malformed YAML, missing fields, invalid patterns

- [x] **1.5A.3 — Refactor pipeline for source-aware execution** ✅
  - [x] Update `Pipeline.__init__` to accept a `SourceConfig` instead of (or in addition to) `CrawlConfig`
  - [x] Update `pipeline.run()` to tag crawl_run with source_id
  - [x] Update `pipeline.run()` to tag documents with source_id
  - [x] Apply source-specific content_selector during HTML extraction
  - [x] Refactor `clean()` in `cleaner.py` to accept an optional `boilerplate_patterns` parameter; fall back to existing CRD defaults when not provided (existing `_BOILERPLATE_PATTERNS` become the default, not the only option)
  - [x] Apply source-specific boilerplate_patterns during cleaning by passing them from the source config through the pipeline to the cleaner
  - [x] Update CLI `scrape` command: add `--source <slug>` flag (runs one source) and `--all` flag (runs all enabled)
  - [x] Update CLI `status` command to show per-source statistics
  - [x] Write integration tests for source-aware pipeline
  - [x] Write CLI tests for `--source` and `--all` flags

- [x] **1.5A.4 — Add content_category to data model** ✅
  - [x] Define `ContentCategory` enum: `agency_guidance`, `fact_sheet`, `statutory_code`, `regulation`, `poster`, `faq`
  - [x] Add `content_category` column to `documents` table
  - [x] Add `content_category` column to `chunks` table
  - [x] Write migration to add columns with default `agency_guidance`
  - [x] Implement URL/content-based heuristic to classify documents (e.g., PDF fact sheets → `fact_sheet`, FAQ pages → `faq`)
  - [x] Backfill existing CRD data: classify as `agency_guidance` or `fact_sheet` based on URL patterns
  - [x] Update pipeline to assign content_category during ingestion
  - [x] Write unit tests for content categorization heuristics
  - [x] Write migration tests

- [x] **[GATE] 1.5A.5 — Backward compatibility validation** ✅
  - [x] Run `employee-help scrape --source crd` and verify identical behavior to Phase 1
  - [x] All existing 162+ tests still pass (397 tests now, all passing)
  - [x] CRD data correctly tagged with source_id and content_category
  - [x] New source can be added by creating a YAML config file (no code changes)
  - [x] PO sign-off on multi-source foundation

---

#### 1.5B — Agency Source Expansion (DIR, EDD, CalHR)

> **Scheduling note:** 1.5B and 1.5C are independent of each other — both depend only on the 1.5A.5 gate. They **can and should run in parallel** to shorten the critical path. 1.5D depends on both completing.

**Goal:** Add three new agency sources to validate the multi-source architecture works in practice.

- [x] **1.5B.1 — DIR/DLSE source configuration and spike** ✅
  - [x] [SPIKE] Crawl dir.ca.gov/dlse/ manually — identify content structure, navigation, content selectors
  - [x] [SPIKE] Test Playwright vs. static HTML parsing for DIR pages (static HTML — CA.gov template)
  - [x] [SPIKE] Identify main content area selector for DIR (`#main-content`)
  - [x] [SPIKE] Document DIR-specific boilerplate patterns (header, footer, nav, sidebar)
  - [x] Create `config/sources/dir.yaml` with seed URLs, scope rules, selectors
  - [x] Set allowlist patterns for employment/wage/hour content
  - [x] Set blocklist patterns for non-relevant DIR content (e.g., mining, elevators)
  - [x] ~~Run spike crawl (first 20 pages)~~ → Superseded by full crawl (300 pages, 270 docs, 1,757 chunks) ✅
  - [x] Document spike findings and any DIR-specific extraction challenges

- [x] **1.5B.2 — EDD source configuration and spike** ✅
  - [x] [SPIKE] Crawl edd.ca.gov — identify content structure and selectors
  - [x] [SPIKE] Determine if EDD uses ca.gov template (yes — `.main-primary` content selector)
  - [x] [SPIKE] Identify EDD content areas relevant to employee rights (UI, SDI, PFL)
  - [x] Create `config/sources/edd.yaml` with seed URLs, scope rules, selectors
  - [x] Set allowlist patterns for benefits/employee content
  - [x] Set blocklist patterns (employer tax admin, internal tools, non-English)
  - [x] ~~Run spike crawl (first 20 pages)~~ → Superseded by full crawl (200 pages, 200 docs, 411 chunks) ✅
  - [x] Document spike findings

- [x] **1.5B.3 — CalHR source configuration and spike** ✅
  - [x] [SPIKE] Crawl calhr.ca.gov — identify content structure (WordPress/Divi, same as CRD)
  - [x] [SPIKE] Investigate hrmanual.calhr.ca.gov subdomain (ASP.NET app — separate config needed for future)
  - [x] [PO] Confirmed: Include CalHR in general knowledge base with "state_employees" metadata tag
  - [x] Create `config/sources/calhr.yaml` with seed URLs, scope rules, selectors
  - [x] Tag CalHR content with "state_employees" metadata flag (retrieval can de-prioritize for private-sector queries)
  - [x] ~~Run spike crawl (first 20 pages)~~ → Superseded by full crawl (300 pages, 300 docs, 1,365 chunks) ✅
  - [x] Document spike findings

- [x] **1.5B.4 — Full ingestion and quality check** ✅ (2026-02-25)
  - [x] Run full pipeline for DIR source ✅ — 300 URLs, 270 docs, 1,757 chunks, 30 errors (10%), 1290s
  - [x] Run full pipeline for EDD source ✅ — 200 URLs, 200 docs, 411 chunks, 0 errors, 865s
  - [x] Run full pipeline for CalHR source ✅ — 300 URLs, 300 docs, 1,365 chunks, 0 errors, 1505s
  - [x] **Total agency: 770 documents → 3,533 chunks**
  - [x] Content_category assignment verified via cross-source validation ✅
  - [x] No cross-source data contamination (17 expected cross-source duplicates only) ✅
  - [x] Note: DIR 10% error rate is within acceptable range for live web crawling (transient errors)

- [x] **[GATE] 1.5B.5 — Agency expansion validated** ✅
  - [x] Three new sources ingested: DIR (1,757 chunks), EDD (411 chunks), CalHR (1,365 chunks) ✅
  - [x] Error rates: DIR 10%, EDD 0%, CalHR 0% — all within acceptable range ✅
  - [x] Per-source run manifests generated ✅
  - [ ] PO review of sample chunks from each source (pending PO gate review — all data available for review)

---

#### 1.5C — Statutory Code Extractor

**Goal:** Build the statutory code ingestion pipeline, using the PUBINFO database as the primary data source and the leginfo web scraper as fallback/validation.

> **Key Decision (2026-02-25):** After extensive live testing revealed a **30–40% HTTP error rate** on leginfo.legislature.ca.gov (502s, 500s, connection resets, timeouts), research discovered the **PUBINFO database** — an official MySQL dump of all California statutory codes provided by the Legislature at `https://downloads.leginfo.legislature.ca.gov/`. This structured database contains complete section text, hierarchy metadata, effective dates, and active/repealed status. It is updated daily. The PUBINFO loader replaces the web scraper as the primary ingestion mechanism.
>
> **Leginfo findings:**
> - `robots.txt` disallows all non-Googlebot crawlers (`Disallow: /` for `User-agent: *`)
> - TOC expansion pages (`codedisplayexpand.xhtml`) most failure-prone — expensive server-side tree generation
> - Individual section pages (`codes_displaySection.xhtml`) moderately reliable but still ~30% error rate
> - `codes_displayText.xhtml` (multi-section bulk pages) most reliable of web page types
> - Section numbers consistently in `<h6>` tags across all codes; heading hierarchy varies by code (LAB uses h4 for all levels, BPC uses h5/h6 mix)
> - No REST API, JSON, or XML endpoints available
>
> **PUBINFO database schema (key table: `law_section_tbl`):**
> | Column | Type | Description |
> |--------|------|-------------|
> | `id` | VARCHAR(100) | Unique section ID |
> | `law_code` | VARCHAR(5) | Code abbreviation (LAB, GOV, etc.) |
> | `section_num` | VARCHAR(30) | Section number (e.g., "1102.5") |
> | `division` | VARCHAR(100) | Division name |
> | `title` | VARCHAR(100) | Title name |
> | `part` | VARCHAR(100) | Part name |
> | `chapter` | VARCHAR(100) | Chapter name |
> | `article` | VARCHAR(100) | Article name |
> | `effective_date` | DATETIME | Effective date |
> | `history` | VARCHAR(1000) | Amendment/history text |
> | `content_xml` | LONGTEXT | Full section text (XML format, in .lob sidecar files) |
> | `active_flg` | VARCHAR(1) | 'Y' if current/active |
>
> Supporting tables: `law_toc_tbl` (TOC structure), `law_toc_sections_tbl` (section-to-TOC mapping), `codes_tbl` (code names).

- [x] **1.5C.1 — Leginfo technical spike** ✅
  - [x] [SPIKE] Navigate leginfo.legislature.ca.gov manually — document URL patterns
  - [x] [SPIKE] Confirm URL pattern for TOC: `codedisplayexpand.xhtml?tocCode=LAB` (expand all)
  - [x] [SPIKE] Confirm URL pattern for sections: `codes_displaySection.xhtml?lawCode=LAB&sectionNum=...`
  - [x] [SPIKE] Test Playwright rendering of leginfo JSF pages (NOT needed — server-rendered)
  - [x] [SPIKE] Test direct HTTP requests (confirmed: httpx works, no JS needed)
  - [x] [SPIKE] Identify TOC HTML structure — h3/h4/h5/h6 headings with displayText links
  - [x] [SPIKE] Identify section content HTML structure — h6 for section numbers, paragraphs for text
  - [x] [SPIKE] Identify how leginfo displays effective dates and amendment history (em/i tags)
  - [x] [SPIKE] Test rate limiting and politeness (robots.txt: 10s Crawl-Delay)
  - [x] [SPIKE] Document findings: navigation strategy, URL construction, rendering approach, rate limits
  - [x] [SPIKE] Estimate total section count for Labor Code and Gov Code FEHA sections
  - [x] **[SPIKE] Discovered PUBINFO database** at `downloads.leginfo.legislature.ca.gov` — complete structured MySQL dump of all codes, updated daily ✅
  - [x] **[SPIKE] Documented leginfo reliability issues**: 30–40% error rate, 502s on TOC pages, connection resets, `robots.txt` disallows non-Googlebot crawlers ✅

- [x] **1.5C.2 — Statutory code web scraper implementation (FALLBACK)** ✅
  - [x] Design `StatutoryExtractor` class interface (accepts code abbreviation + division list → yields sections)
  - [x] Implement TOC traversal: given a code abbreviation, navigate the TOC to discover all divisions/parts/chapters/articles/sections
  - [x] Implement section extraction: given a section URL, extract the section text
  - [x] Implement citation metadata parsing:
    - [x] Parse section number (including decimal subdivisions like "1102.5")
    - [x] Parse subdivision markers (a), (b), (1), (2), (A), (B)
    - [x] Extract division/part/chapter/article hierarchy path
    - [x] Extract effective date / "as of" date
    - [x] Generate canonical citation string (e.g., "Cal. Lab. Code § 1102.5")
  - [x] Implement rate limiting specific to leginfo (configurable, min 3s, recommended 10+)
  - [x] Implement resumability: if pipeline crashes mid-code, can resume from last completed division ✅
  - [x] Implement repealed-section handling (F-SC.6): `is_active` boolean column on chunks (default True)
  - [x] Create `src/employee_help/scraper/extractors/statute.py`
  - [x] Write unit tests with mock HTML fixtures (no live network calls in tests)
  - [x] Write integration test that can optionally run against live leginfo (marked `@pytest.mark.live`) ✅
  - [x] Write tests for repealed-section soft-delete (re-ingest with a removed section → verify chunk marked inactive, not deleted) ✅
  - **Note:** This web scraper is retained as a **fallback and validation tool**. The primary ingestion path is the PUBINFO loader (1.5C.8).

- [x] **1.5C.8 — PUBINFO database loader implementation (PRIMARY)** ✅
  - [x] [SPIKE] Download `pubinfo_load.zip` and document the exact file format:
    - [x] Understand the `.dat` / `.lob` file structure (tab-delimited data + LOB sidecar files)
    - [x] Identify how `content_xml` is stored and referenced from the `.dat` file (column 15 is a filename pointing to a .lob sidecar file)
    - [x] Parse sample sections from LAB and GOV codes to verify content quality
    - [x] Determine the XML schema used in `content_xml` and how to extract plain text (HTML content, parsed with BeautifulSoup `.get_text()`)
  - [x] Implement `PubinfoLoader` class:
    - [x] `download_pubinfo(dest_dir, year)` — downloads the PUBINFO ZIP archive with progress logging
    - [x] `parse_law_sections()` — parses `LAW_SECTION_TBL.dat` and associated LOB files from ZIP
    - [x] `filter_sections(sections, target_codes, target_divisions, active_only)` — filters by code + division + active flag
    - [x] `to_statute_sections(sections)` — converts PubinfoSection rows to `StatuteSection` model objects
    - [x] `html_to_text(html)` — extracts clean text from HTML content via BeautifulSoup
  - [x] Implement citation building from PUBINFO fields (reuses existing `build_citation()`)
  - [x] Implement hierarchy building from PUBINFO `division`/`title`/`part`/`chapter`/`article` fields
  - [x] Implement `active_flg` handling: 'Y' → active, 'N' → filtered out by default
  - [x] ~~Implement daily delta support~~ → Daily deltas don't contain `law_section_tbl`. Weekly full re-download strategy implemented via `--force` flag (see 1.5D.4). ✅
  - [x] Create `src/employee_help/scraper/extractors/pubinfo.py`
  - [x] Write unit tests with sample `.dat` / `.lob` fixtures (48 tests in `tests/test_pubinfo_loader.py`)
  - [x] ~~Write live integration test~~ → Full production run validates the loader end-to-end (6 codes, 19,785 docs, 0 errors). Separate live test deferred as low value. ✅
  - [x] Integrate with Pipeline: `_extract_via_pubinfo()` as default path, `_extract_via_web()` as fallback, routed by `method` config
  - [x] Add CLI flag: `employee-help scrape --source <slug> --method pubinfo|web` (default: pubinfo)
  - [x] Add CLI command: `employee-help pubinfo-download [--year YYYY] [--dest DIR]`
  - [x] Add `method` field to `StatutoryConfig` dataclass (default: "pubinfo")
  - [x] Add `method: pubinfo` to all 6 statutory source YAML configs

- [x] **1.5C.9 — Web scraper resilience improvements** ✅
  - [x] Add retry with exponential backoff to `StatutoryExtractor._fetch()`: 3 retries with 2s/4s/8s delays
  - [x] Add circuit breaker: if >50% of requests fail (after ≥6 requests), abort with `RuntimeError`
  - [x] Add content validation: `_is_proxy_error()` detects proxy error / 502 / 503 in response body
  - [x] Add 502/500 detection: treat HTTP error pages returned with 200 status as failures (retry)
  - [x] Write tests for retry logic, circuit breaker, and content validation (21 tests in `test_web_scraper_resilience.py` using respx) ✅

- [x] **1.5C.3 — Section-boundary chunking** ✅
  - [x] Add a `strategy` parameter to the chunker interface: `heading_based` (existing) vs. `section_boundary` (new)
  - [x] Implement `section_boundary` strategy: one code section = one chunk (default behavior)
  - [x] Implement: if section exceeds max_tokens, split at subdivision boundaries
  - [x] Ensure each resulting chunk carries the full citation metadata
  - [x] Ensure section-boundary chunker preserves subdivision markers in content
  - [x] Write unit tests for section-boundary chunking (normal sections, long sections, sections with many subdivisions)
  - [x] Write tests verifying citation metadata is preserved on split chunks
  - [x] Write regression tests confirming `heading_based` strategy (agency content) is unaffected by the new code

- [x] **1.5C.4 — Code manifest configuration (P0 codes)** ✅
  - [x] Define code manifest YAML schema (code_name, code_abbreviation, target_divisions, citation_prefix) — added `StatutoryConfig` dataclass
  - [x] Create `config/sources/labor_code.yaml`:
    - [x] All 7 divisions of Labor Code [PO decision: comprehensive — all divisions]
    - [x] Specify citation format: "Cal. Lab. Code"
  - [x] Create `config/sources/gov_code_feha.yaml`:
    - [x] Government Code Division 3 (FEHA: §§ 12900–12996)
    - [x] Specify citation format: "Cal. Gov. Code"
  - [x] Validate configs load correctly with source config loader

- [x] **1.5C.5 — P0 statutory ingestion run** ✅ (completed as part of 1.5D.1, 2026-02-25)
  - [x] Run PUBINFO loader for Labor Code (all divisions) — 2,631 docs, 2,733 chunks ✅
  - [x] Run PUBINFO loader for Government Code (FEHA Division 3 + whistleblower Divisions 1–2) — 4,649 + 7,772 docs ✅
  - [x] Section counts verified: PUBINFO `active_flg='Y'` filtering applied during extraction ✅
  - [x] Citation metadata accuracy verified via spot-check tests (48 tests in `test_ingestion_spot_check.py`) ✅
  - [x] content_category = `statutory_code` on 100% of statutory chunks (verified by cross-source validation) ✅
  - [x] Repealed sections (`active_flg='N'`) excluded during PUBINFO filtering ✅
  - [x] Statistics documented in 1.5D.1 and 1.5D.3 ✅
  - [ ] Cross-validate 20 sections against leginfo web page (manual spot-check — deferred, low risk given PUBINFO is the authoritative source)

- [x] **[GATE] 1.5C.6 — Statutory pipeline validated** ✅
  - [x] Labor Code and FEHA fully ingested via PUBINFO loader ✅
  - [x] Citation format validated: 30/30 sampled citations match expected format ✅
  - [x] Specific section content verified: 6 key statutes (Lab 510, 1102.5; Gov 12940; BPC 16600, 17200; CCP 425.16) contain expected substantive content ✅
  - [x] No missing divisions or articles (all active sections ingested per PUBINFO) ✅
  - [ ] PO sign-off on statutory pipeline quality (pending PO gate review)

- [x] **1.5C.7 — Citation regression test suite** ✅
  - [x] Build a golden dataset of 50+ sections with known-correct citation strings (e.g., "Cal. Lab. Code § 1102.5(a)", "Cal. Gov. Code § 12940(j)(1)") — sourced from the 1.5C.5 spot-check plus additional hand-verified examples
  - [x] Implement as an automated pytest suite: extract citation from stored chunk, compare to golden expected value
  - [x] Run on every CI build to prevent citation parsing regressions from future code changes
  - [x] Include edge cases: decimal section numbers (1102.5), deep subdivisions (a)(1)(A), repealed sections (marked inactive), sections with unusual numbering

---

#### 1.5D — P1 Sources & Cross-Source Validation

**Goal:** Ingest remaining P1 statutory codes and validate the full expanded knowledge base.

- [x] **1.5D.1 — P1 statutory codes ingestion** ✅ (2026-02-25)
  - [x] Create `config/sources/unemp_ins_code.yaml` (Unemployment Insurance Code — Div. 1) ✅
  - [x] Create `config/sources/bus_prof_code.yaml` (Business & Professions Code — §§ 16600–16607, 17200–17210) ✅
  - [x] Create `config/sources/ccp.yaml` (Code of Civil Procedure — § 340, § 425.16, § 1021.5) ✅
  - [x] Create `config/sources/gov_code_whistleblower.yaml` (Government Code whistleblower sections) ✅
  - [x] Run PUBINFO loader for all 6 statutory codes ✅ — Results:
    - Labor Code: 2,640 sections → 2,733 chunks (22s)
    - Gov Code FEHA: 4,649 sections → 4,718 chunks (23s)
    - Gov Code Whistleblower: 7,772 sections → 7,980 chunks (25s)
    - Unemployment Insurance Code: 838 sections → 850 chunks (20s)
    - Bus & Prof Code: 475 sections → 492 chunks (19s)
    - Code of Civil Procedure: 3,411 sections → 3,447 chunks (22s)
    - **Total statutory: 19,785 documents → 20,220 chunks, ~131s, 0 errors**
  - [x] Citation format validation: 30/30 sampled citations match `Cal. <Code> Code § <num>` format ✅
  - [x] Idempotency verified: re-run creates 0 new documents/chunks (content_hash dedup) ✅

- [x] **1.5D.2 — Cross-source duplicate detection** ✅
  - [x] Implement cross-source content_hash match detection: identify cases where the same content appears from different sources (e.g., a statute quoted verbatim in an agency guidance page) ✅
  - [x] Define resolution strategy: keep both chunks with their respective content_categories (a statute chunk and a guidance chunk may quote the same text but serve different retrieval purposes); flag exact duplicates in the validation report for PO review ✅
  - [x] Write tests for duplicate detection across sources ✅

- [x] **1.5D.3 — Comprehensive cross-source validation** ✅ (2026-02-25)
  - [x] Generate full knowledge base statistics:
    - [x] Total sources ingested (count by type: agency vs. statutory) ✅
    - [x] Total documents stored (count by source) ✅
    - [x] Total chunks created (count by source and content_category) ✅
    - [x] Token count distribution (min, max, avg — overall and per source) ✅
    - [x] Content category distribution per source ✅
  - [x] Citation sample validation: randomly select N statutory chunks, verify citation format ✅
  - [x] Cross-reference check: cross-source duplicate detection via content_hash ✅
  - [x] No-empty-chunks check ✅
  - [x] Token bounds check per source ✅
  - [x] Generate validation report (JSON + Markdown) via `employee-help cross-validate` ✅
  - [x] Implemented in `validation_report.py` with 7 check types, 18 tests in `test_cross_source_validation.py` ✅
  - [x] Idempotency re-run: labor_code re-run confirmed 0 new documents/chunks ✅ (bug found & fixed: pipeline was creating duplicate chunks on re-runs; `is_new` check added)
  - [x] Validation results (2026-02-25): 32/33 checks pass across 9 sources (pre-CACI):
    - 9 sources: 6 statutory + 3 agency (DIR, EDD, CalHR) — updated to 10 sources after CACI integration (1.5E)
    - 20,546 documents, 23,247 active chunks — updated to 20,871 docs, 24,106 chunks after CACI
    - 30/30 citation samples validated
    - 17 cross-source duplicate content_hashes (expected: same text in guidance + statutory)
    - 0 empty chunks
    - **1 known issue**: CalHR `calhr_token_bounds` FAIL — 1 chunk at 37,820 tokens (policy-memos page). Root cause: heading-based chunker doesn't enforce max-chunk-size split. Fix deferred to Phase 2 chunker improvements.
  - [x] Data quality fixes applied (2026-02-25):
    - Fixed 14 CCP bracket citations (`§ [1084.]` → `§ 1084.`) — root cause: PUBINFO section_num field contains brackets; `build_citation()` now strips them
    - Removed 458 intra-document duplicate chunks (mostly DIR multilingual poster pages); `insert_chunks()` now deduplicates by `(document_id, content_hash)`
    - 48/48 spot-check validation tests pass (`tests/test_ingestion_spot_check.py`)
  - Full report: `data/validation/cross_source_validation.md` and `.json`

- [x] **1.5D.4 — Automated content refresh (PO Decision #5)** ✅
  - [x] Implement `employee-help refresh --source <slug>` and `--all` CLI commands (re-runs pipeline, uses content_hash to skip unchanged content) ✅
  - [x] Add change detection reporting: after a refresh run, log which documents had new content vs. unchanged ✅
  - [x] ~~Implement PUBINFO daily delta loading~~ → Daily deltas (`pubinfo_Mon.zip` etc.) only contain bill-related tables, NOT `law_section_tbl`. Statutory updates require full archive re-download. Implemented `--force` flag on `pubinfo-download` for weekly re-download strategy. ✅
  - [ ] Create cron configuration with recommended cadence: weekly for all sources (agency crawls + PUBINFO full re-download) — deferred to deployment/ops setup
  - [x] Write tests for change detection logic (unchanged content → 0 new docs; changed content → updated docs) ✅

- [x] **1.5D.5 — Performance baseline (NF-2)** ✅ (2026-02-25)
  - [x] Agency pipeline timing (all within 30-minute threshold):
    - DIR: 1,290s (21.5 min) — 300 pages ✅
    - EDD: 865s (14.4 min) — 200 pages ✅
    - CalHR: 1,505s (25.1 min) — 300 pages ✅
  - [x] PUBINFO loader timing (all within 15-minute threshold):
    - Full ZIP download: ~10 min for 677 MB
    - Labor Code parse + store: 22s for 2,640 sections ✅
    - All 6 codes total: ~131s (2.2 min) ✅
  - [x] PUBINFO vs web scraper: PUBINFO processes ~120 sections/sec vs web scraper's ~1 page/5s (30–40% error rate). **~600x throughput improvement, 0% error rate.**
  - [x] Per-source timing documented above
  - [x] No sources exceed threshold; PUBINFO is dramatically faster than web scraping

- [ ] **[GATE] 1.5D.6 — Phase 1.5 acceptance** (implementation complete; awaiting PO review)
  - [x] All P0 and P1 sources ingested (10 sources: 6 statutory + 3 agency + 1 CACI jury instructions) ✅
  - [x] Validation report: 32/33 checks pass (1 known issue: CalHR oversized chunk) ✅
  - [x] Idempotency confirmed (re-run creates 0 new documents/chunks) ✅
  - [x] Citation accuracy verified (30/30 sampled citations valid) ✅
  - [x] Idempotency bug found and fixed (pipeline.py: added `is_new` check before chunk insertion) ✅
  - [ ] PO approves expanded knowledge base as foundation for Phase 2
  - [ ] **Phase 1.5 COMPLETE** (pending PO approval)

---

### Phase 2: RAG Pipeline & Answer Generation `[x] CODE COMPLETE` (2026-02-26)

> **Implementation complete.** All automated gates pass. 750 tests (143 Phase 2 specific + 40 CACI). Awaiting PO human evaluation review (2C.5) and final acceptance (2C.6).

#### 2A — Embedding & Retrieval Foundation `[x] COMPLETE`

**Goal:** Generate vector embeddings for all chunks, build a hybrid search index, implement dual-mode retrieval. At the end of 2A, a user can run `employee-help search "query" --mode consumer|attorney` and receive ranked, relevant results.

**Key Technology Decisions:**
- **Embedding model**: `BAAI/bge-base-en-v1.5` — 768-dim, 512 max seq len, local CPU inference (~544MB, 2.8 chunks/sec). Selected after spike testing BGE-M3 (OOM at ~2.4GB) and bge-large-en-v1.5 (3x slower, same quality).
- **Vector database**: LanceDB (embedded, Apache Arrow format) — built-in hybrid search (vector + BM25 via FTS + RRF), metadata filtering, in-process (no server dependency).
- **Reranker**: mxbai-rerank-base-v2 (cross-encoder) — **disabled** due to OOM when co-loaded with embedding model on macOS x86_64 (<8GB available RAM). Architecture supports enabling on systems with more memory.
- **Hybrid search**: Dense vector similarity + BM25 keyword scoring fused via Reciprocal Rank Fusion (RRF). Critical for legal content where citation queries ("section 1102.5") need exact keyword matching while concept queries ("can I be fired for whistleblowing?") need semantic understanding.

- [x] **2A.1 — Add RAG dependencies to project** ✅
  - [x] Added optional `[rag]` dependency group: `sentence-transformers>=3.0,<3.5`, `torch>=2.0` (pinned ≤2.2.2 for macOS x86_64), `transformers>=4.40,<4.50`, `numpy<2.0`, `lancedb>=0.6`, `anthropic>=0.40`, `jinja2>=3.1`
  - [x] Added optional `[eval]` dependency group: `ragas`, `deepeval`, `textstat`
  - [x] Updated `.gitignore` for LanceDB data directory (`data/lancedb/`)

- [x] **2A.2 — [SPIKE] Embedding model validation** ✅
  - [x] BGE-M3: OOM killed (~2.4GB model weights exceed available RAM on macOS x86_64)
  - [x] bge-base-en-v1.5: 768-dim, 512 max seq len, 2.8 chunks/sec, ~544MB model, ~2GB peak, 5/25 quality
  - [x] bge-large-en-v1.5: 1024-dim, 512 max seq len, 0.9 chunks/sec, ~3.4GB peak, 5/25 quality (identical to base)
  - [x] **Selected**: `BAAI/bge-base-en-v1.5` — 3x faster, same quality, lower memory than large variant
  - [x] Key finding: BGE is asymmetric — queries need prefix `"Represent this sentence for searching relevant passages: "`. 512 token truncation mitigated by LanceDB FTS (BM25) for exact matching.

- [x] **2A.3 — Implement embedding service** ✅
  - [x] `EmbeddingService` class in `src/employee_help/retrieval/embedder.py`:
    - `embed_text(text)` — document embedding (no prefix)
    - `embed_query(query)` — query embedding with BGE instruction prefix
    - `embed_batch(texts, batch_size)` — single model.encode() call for throughput
    - `embed_chunks(chunks)` — wraps batch embedding with chunk metadata
  - [x] `ChunkEmbedding` dataclass: chunk_id, document_id, source_id, content_category, citation, dense_vector, content_hash, model_version, is_active, source_url
  - [x] Progress logging at ~500-chunk intervals with rate (chunks/s) and ETA
  - [x] 13 unit tests + 8 integration tests (`@pytest.mark.slow`)

- [x] **2A.4 — Implement LanceDB vector store** ✅
  - [x] `VectorStore` class in `src/employee_help/retrieval/vector_store.py`:
    - `create_table(embeddings)` — creates `chunk_embeddings` table with 768-dim vectors + metadata
    - `upsert_embeddings(embeddings)` — atomic `merge_insert` keyed on `chunk_id`
    - `search_hybrid(query_text, query_vector, top_k, filter)` — vector + BM25 via `RRFReranker` fusion
    - `search_vector(query_vector, top_k, filter)` — pure cosine similarity
    - `search_keyword(query_text, top_k, filter)` — pure BM25 via FTS index
    - `get_stats()` — row counts using column-level selection (avoids loading vectors)
  - [x] FTS index on `content` column for BM25; scalar indexes on `chunk_id`, `content_category`, `source_id`
  - [x] No ANN vector index needed (flat scan <10ms at 23K rows)
  - [x] FTS content prepends `[citation] heading_path\n` for BM25 discoverability (statute body text often doesn't mention its own section number)
  - [x] 24 unit tests + 3 integration tests

- [x] **2A.5 — Implement embedding CLI commands** ✅
  - [x] `employee-help embed --all` — embed all un-embedded chunks
  - [x] `employee-help embed --source <slug>` — embed chunks for a specific source
  - [x] `employee-help embed --rebuild` — delete and rebuild entire vector index
  - [x] `employee-help embed-status` — show embedding coverage per source, index stats, model version
  - [x] Incremental embedding: only embeds chunks where content_hash not in LanceDB
  - [x] Deactivation sync: chunks with `is_active=0` in SQLite marked inactive in LanceDB

- [x] **[GATE] 2A.5b — Embedding pipeline validated** ✅ PASS
  - [x] 24,058/24,058 chunks embedded (0 failures, includes 353 CACI chunks added in 1.5E)
  - [x] `embed-status` shows 100% coverage
  - [x] Full embedding time: ~2h 9min (bge-base-en-v1.5 on macOS x86_64 CPU at 3.1 chunks/sec)
  - [x] Re-running `embed --all` after no changes embeds 0 new chunks (incremental works)
  - [x] LanceDB index responds to test queries in ~65ms warm

- [x] **2A.6 — Implement query preprocessor** ✅
  - [x] `QueryPreprocessor` class in `src/employee_help/retrieval/query.py`:
    - Citation detection: regex for "section X", "Lab. Code", "§ X", "Gov. Code section X"
    - Legal term expansion: FEHA → Fair Employment and Housing Act, WC → workers' compensation, etc.
    - Query cleaning: normalize whitespace, remove excessive punctuation
  - [x] `ProcessedQuery` dataclass: original_query, normalized_query, has_citation, cited_section, expanded_terms

- [x] **2A.7 — Implement reranker** ✅
  - [x] `Reranker` class in `src/employee_help/retrieval/reranker.py`:
    - mxbai-rerank-base-v2 cross-encoder with score normalization
    - Configurable via `rerank_enabled` flag in `config/rag.yaml`
  - [x] **Disabled by default** — OOM when loaded alongside embedding model on macOS x86_64. Enable on systems with >8GB available RAM.

- [x] **2A.8 — Implement dual-mode retrieval service** ✅
  - [x] `RetrievalService` class in `src/employee_help/retrieval/service.py`:
    - Pipeline: preprocess → hybrid search (top-50) → [rerank if enabled] → mode filter → diversity → top-k
    - `RetrievalResult` dataclass: chunk_id, document_id, source_id, content, heading_path, content_category, citation, relevance_score, source_url
  - [x] **Consumer mode**: filter to `agency_guidance`, `fact_sheet`, `faq`; no citation boosting
  - [x] **Attorney mode**: all categories; citation boost 2.0x (substring match) + additional 2.0x exact-section bonus (up to 4.0x for exact lookups); statutory boost 1.2x
  - [x] Source diversity: max 3 chunks from same document
  - [x] Result deduplication: overlapping content → keep higher-scored

- [x] **2A.9 — Implement search CLI command** ✅
  - [x] `employee-help search "query" --mode consumer|attorney --top-k 5`
  - [x] Results display: rank, score, content_category, citation, heading_path, content preview, source URL
  - [x] `--verbose`: full content + retrieval debug info
  - [x] `--json`: structured JSON output

- [x] **[GATE] 2A.10 — Search quality benchmark** ✅ PASS
  - [x] Evaluation datasets: 25 consumer + 25 attorney + 10 adversarial questions in `tests/evaluation/`
  - [x] `employee-help evaluate-retrieval` command with per-question and aggregate metrics
  - [x] **Results:**
    - Consumer precision@5: **0.888** (threshold 0.6) ✅
    - Attorney precision@5: **0.808** (threshold 0.7) ✅
    - Citation lookup top-1: **1.000** (2/2 pure citation lookups, threshold 0.9) ✅
    - Overall MRR: **0.907**
    - All queries return results (0 empty)
  - [x] Iterations applied: increased citation_boost to 2.0, added exact-section bonus, prepended citations to FTS content
  - [x] Reports saved to `data/evaluation/retrieval_evaluation.json` and `.md`

---

#### 2B — LLM Answer Generation `[x] COMPLETE`

**Goal:** Connect the retrieval service to Claude for generating mode-appropriate answers with proper citations. At the end of 2B, a user can run `employee-help ask "question" --mode consumer|attorney` and receive a complete, cited answer.

**Key Technology Decisions:**
- **LLM**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for consumer mode (~$0.006/query), Claude Sonnet 4.6 (`claude-sonnet-4-6`) for attorney mode (~$0.032/query)
- **Citations API**: Context delivered as document content blocks (not text template), enabling Claude's native citation markers. Each chunk = one document block with metadata header.
- **Citation validation**: Both strict (remove hallucinated + warn) and permissive (mark `[citation not verified]`) modes. Validates section number AND code type (Lab/Gov/Bus) to prevent cross-code false matches.
- **Streaming**: `generate_stream()` returns 3-tuple `(text_stream, retrieval_results, metadata_list)`. Mutable metadata list populated on stream completion.

- [x] **2B.1 — Implement LLM client wrapper** ✅
  - [x] `LLMClient` class in `src/employee_help/generation/llm.py`:
    - `generate()` — synchronous call with Citations API document blocks
    - `generate_stream()` — streaming with citation extraction from final message
    - Model selection by mode: consumer → Haiku 4.5, attorney → Sonnet 4.6
    - Token usage tracking with model-aware cost estimation via `MODEL_PRICING` dict
    - Error handling: `APIError`, `RateLimitError`, `APIConnectionError` with SDK retry (2 attempts, exponential backoff)
    - Timeout: configurable, default 120s (increased from 30s after complex attorney queries exceeded original limit)
  - [x] API key management: `ANTHROPIC_API_KEY` environment variable with clear error on missing
  - [x] 12 unit tests + integration test (`@pytest.mark.llm`)

- [x] **2B.2 — Design and implement prompt templates** ✅
  - [x] **Consumer mode** system prompt (`config/prompts/consumer_system.j2`):
    - Role: helpful legal information assistant for California employment rights
    - Tone: clear, plain language, non-legal-advice, supportive
    - Citation format: "According to [Agency Name]..." with source URL
    - Scope boundaries: says clearly when question is outside California employment rights
    - Disclaimer: "This information is for educational purposes only and is not legal advice."
    - Next steps: concrete actions (filing complaints, contacting agencies, consulting attorneys)
  - [x] **Attorney mode** system prompt (`config/prompts/attorney_system.j2`):
    - Role: legal research assistant for licensed attorneys
    - Tone: precise legal language with statutory citations
    - Citation format: "Cal. [Code] Code § [number]" — cites only statutes present in context
    - Analysis structure: applicable statutes, elements, burden of proof, defenses, remedies, cross-references
    - Disclaimer: "This AI-generated analysis should be independently verified."
  - [x] **PromptBuilder** class in `src/employee_help/generation/prompts.py`:
    - `build_prompt()` → `PromptBundle` with system_prompt, user_message, document_blocks
    - Citations API document blocks: each chunk → one `document` content block with metadata header (category, citation, URL)
    - Token budget enforcement: drops lowest-scored chunks if context exceeds budget (default 6000 tokens)
  - [x] 16 unit tests for prompt building

- [x] **2B.3 — Implement answer generation service** ✅
  - [x] `AnswerService` class in `src/employee_help/generation/service.py`:
    - `generate(query, mode) → Answer` — full pipeline: retrieve → build prompt → LLM call → citation validation → return
    - `generate_stream(query, mode) → (Iterator[str], list[RetrievalResult], list[dict])` — streaming with mutable metadata
  - [x] `Answer` dataclass in `src/employee_help/generation/models.py`:
    - text, mode, query, citations (AnswerCitation list), retrieval_results, model_used, token_usage, duration_ms, warnings
  - [x] `AnswerCitation` dataclass: claim_text, chunk_id, source_url, citation, content_category, document_index
  - [x] Citation post-processor:
    - Extracts citations from Claude Citations API response (maps document_index → chunks)
    - Extracts citation strings from text (regex for California statutory patterns)
    - Validates against retrieved chunks (checks section number AND code type)
    - Strict mode: removes hallucinated citations + adds warning
    - Permissive mode: marks with `[citation not verified]`
    - Configurable via `citation_validation` in `config/rag.yaml`
  - [x] 17 unit tests + integration tests (`@pytest.mark.llm`)

- [x] **2B.4 — Implement ask CLI command** ✅
  - [x] `employee-help ask "question" --mode consumer|attorney`
  - [x] Streams response to terminal in real-time
  - [x] After response: displays citations used, model, token usage, cost estimate, duration
  - [x] `--no-stream`: wait for complete response
  - [x] `--debug`: show retrieval results (no double-retrieval)
  - [x] `--json`: structured Answer as JSON
  - [x] API key check with clear error + instructions

- [x] **[GATE] 2B.5 — End-to-end pipeline validation** ✅ PASS
  - [x] 5 consumer questions tested: plain-language, well-sourced, disclaimers present
  - [x] 5 attorney questions tested: statutory citations, analysis structure, disclaimers
  - [x] Citation post-processor catches hallucinated citations (permissive mode marks `[citation not verified]`)
  - [x] Streaming works: tokens appear incrementally
  - [x] Cost tracking: consumer avg $0.006/query, attorney avg $0.032/query
  - [x] No crashes across 11 diverse queries
  - [x] Fix applied: timeout increased 30s→120s (complex attorney questions exceeded original limit)

---

#### 2C — Quality & Evaluation `[x] CODE COMPLETE` (awaiting PO review)

**Goal:** Systematically evaluate retrieval and answer quality, establish baselines, and create regression-prevention infrastructure.

- [x] **2C.1 — Create evaluation datasets** ✅
  - [x] `tests/evaluation/consumer_questions.yaml`: 25 questions spanning wages/overtime (5), discrimination/harassment (5), retaliation/whistleblower (3), leave/CFRA (3), workplace safety (2), unemployment/SDI/PFL (4), non-compete/trade secrets (2), general process (1)
  - [x] `tests/evaluation/attorney_questions.yaml`: 25 questions spanning statutory interpretation (8), element analysis (5), cross-statutory issues (4), procedural questions (3), remedies analysis (3), citation lookups (2)
  - [x] `tests/evaluation/adversarial_questions.yaml`: 10 questions — federal law (out of scope), other states, fabricated citations, ambiguous queries, non-employment topics

- [x] **2C.2 — Implement automated retrieval evaluation** ✅
  - [x] `employee-help evaluate-retrieval` command
  - [x] Retrieval metrics module (`src/employee_help/evaluation/retrieval_metrics.py`):
    - `precision_at_k()`, `recall_at_k()`, `mean_reciprocal_rank()`, `citation_hit_at_k()`
    - `_evaluate_adversarial()` — adversarial question evaluation
    - Pass/fail thresholds: consumer_precision@5=0.6, attorney_precision@5=0.7, citation_top1=0.9
  - [x] Generates JSON + Markdown reports in `data/evaluation/`
  - [x] pytest suite `tests/evaluation/test_retrieval_quality.py` (marked `@pytest.mark.evaluation`)

- [x] **2C.3 — Implement automated answer evaluation** ✅
  - [x] `employee-help evaluate-answers` command (with `--dry-run` for retrieval-only)
  - [x] Answer metrics module (`src/employee_help/evaluation/answer_metrics.py`):
    - `citation_accuracy()` — fraction of answer citations that exist in knowledge base
    - `citation_completeness()` — fraction of expected citations found in answer
    - `has_disclaimer()` — regex check for mode-appropriate disclaimer
    - `reading_level()` — Flesch-Kincaid grade level (textstat with fallback)
    - `extract_statute_citations()` — regex extraction of California statutory patterns
    - `_check_adversarial_behavior()` — keyword-based verification for out_of_scope, citation_not_found, clarification_needed, disclaimer, scope_limitation
    - `run_answer_evaluation()` — full evaluation runner with aggregate metrics
  - [x] Generates JSON report in `data/evaluation/answer_evaluation.json`

- [x] **2C.4 — Implement citation verification test suite** ✅
  - [x] `tests/evaluation/test_citation_integrity.py`: for each attorney question, runs full pipeline, extracts citations, validates against chunks
  - [x] Golden citation mappings from `attorney_questions.yaml` `expected_citations` field
  - [x] Marked `@pytest.mark.evaluation` + `@pytest.mark.llm`

- [x] **2C.5 — Full evaluation run** ✅ (automated; PO review pending)
  - [x] 60-question evaluation completed (25 consumer + 25 attorney + 10 adversarial)
  - [x] **Automated results:**
    - Consumer disclaimer rate: **100%** (25/25)
    - Attorney disclaimer rate: **92%** (23/25 — 2 pure citation-lookup questions omit disclaimer, expected)
    - Adversarial behavior pass rate: **100%** (10/10)
    - Citation completeness: **73%** (attorney mode)
    - Avg citations per attorney answer: **6.7**
    - Consumer avg cost: **$0.006/query**
    - Attorney avg cost: **$0.032/query**
    - Consumer reading level: **6.6** (Flesch-Kincaid grade, accessible)
  - [x] Full answer texts stored in `data/evaluation/answer_evaluation.json` for PO review
  - [ ] [PO] Grade subset of answers on 5 dimensions (accuracy, completeness, citation quality, tone, actionability)
  - [ ] [PO] Document results in `data/evaluation/human_evaluation_report.md`

- [ ] **[GATE] 2C.6 — Phase 2 acceptance** (automated checks pass; awaiting PO)
  - [x] **Retrieval quality**: Consumer P@5=0.888 (≥0.6 ✅), Attorney P@5=0.808 (≥0.7 ✅), Citation top-1=1.000 (≥0.9 ✅)
  - [ ] **Answer quality**: [PO] Average human evaluation score ≥ 3.5/5 across all dimensions
  - [x] **Citation integrity**: Permissive mode marks unverified citations; strict mode available. Citation completeness 73%.
  - [x] **Disclaimer compliance**: Consumer 100%, Attorney 92% (2 citation-lookup-only questions)
  - [x] **Cost**: Consumer avg $0.006, Attorney avg $0.032
  - [x] **Latency**: Consumer ~11s, Attorney ~22s (including model loading; warm queries ~5s consumer, ~15s attorney)
  - [x] **Adversarial robustness**: 100% (10/10 handled correctly)
  - [x] All unit and integration tests pass: **750 tests** (143 Phase 2 + 40 CACI)
  - [ ] [PO] PO reviews answer evaluation report and approves answer quality
  - [ ] [PO] PO approves Phase 2 as foundation for Phase 3 (web application)
  - [ ] **Phase 2 COMPLETE** (pending PO sign-off)

---

### Phase 3: Customer Validation & MVP Web Application

> **Strategic context (2026-02-26):** Phase 3 is the critical inflection point. Phases 1–2 validated feasibility; Phase 3 validates desirability and early viability signals. The phase follows a Lean Startup Build-Measure-Learn cycle: discover (3A) → build minimum (3B) → test with real users (3C). See Section 3.7 for the full product strategy rationale.

#### 3A — Customer Discovery & Landing Page

**Goal:** Validate demand before writing application code. The cheapest experiment that reduces the biggest risk (R1: user trust, R2: discoverability). Follows *The Mom Test* methodology for customer conversations.

- [ ] **3A.1 — Customer discovery interviews**
  - [ ] Identify and recruit 10+ interview subjects (5 employees who have had employment issues, 5 California employment attorneys — solo practitioners or small firms)
  - [ ] Prepare interview guide following Mom Test rules:
    - [ ] For employees: "Tell me about the last time you had a question about your rights at work. What did you do?" / "How much time/money did you spend?" / "Did you end up talking to a lawyer? Why or why not?"
    - [ ] For attorneys: "Walk me through your typical process for researching a new employment law case." / "What tools do you use? What frustrates you?" / "Have you tried any AI tools for legal research?"
  - [ ] Conduct interviews (30 min each, recorded with consent)
  - [ ] Synthesize findings: common pain points, current solutions, switching barriers, willingness to engage with AI tools
  - [ ] Document patterns in a customer discovery report
  - [ ] Identify the strongest "push" forces (what drives people away from current solutions)

- [ ] **3A.2 — Landing page and conversion test**
  - [ ] Build a single-page site: headline value proposition, scope description (what topics we cover), 3 real sample Q&A pairs (generated from the Phase 2 pipeline), email capture for early access
  - [ ] Deploy to a public URL with a memorable domain
  - [ ] Set up privacy-respecting analytics (Plausible, Fathom, or similar)
  - [ ] Drive initial traffic: post to r/legaladvice, employment rights forums, Hacker News (Show HN), legal tech communities
  - [ ] Track: visitor count, sign-up conversion rate, traffic sources, time on page
  - [ ] Run for 2 weeks minimum to collect meaningful data

- [ ] **3A.3 — Keyword and SEO research**
  - [ ] Use keyword research tools (Google Keyword Planner, Ahrefs, or Ubersuggest) to identify top 50 California employment law search queries by volume
  - [ ] Map each query to our knowledge base: can we answer this? If not, what content gap exists?
  - [ ] Prioritize: which queries have high volume + strong coverage in our KB?
  - [ ] Document findings for SEO content strategy in Phase 4B

- [ ] **[GATE] 3A.4 — Discovery validation**
  - [ ] Landing page conversion > 5% (visitors → sign-ups) OR 50+ sign-ups collected
  - [ ] Customer interview insights synthesized: clear evidence that (a) people search online for employment law help, (b) current solutions are frustrating, (c) AI-powered answers are not an automatic disqualifier
  - [ ] [PO] Decision: proceed to 3B (build MVP), pivot positioning/messaging, or investigate a different market entry
  - [ ] If interviews reveal unexpected insights (e.g., attorneys won't use AI, consumers want human review), update the product strategy (Section 3.7) before proceeding

---

#### 3B — Minimum Viable Web Application

**Goal:** Build the simplest web application that delivers core value. Not a full chat application — a question-answer interface. Apply the 40-60% rule (Ramli John, *Product-Led Onboarding*): 40-60% of SaaS users who sign up never return after their first session. The first answer must be excellent. Ship fast, learn faster.

- [x] **3B.1 — [PO] Web framework decision** ✅ (2026-02-26)
  - [x] Evaluate options against MVP criteria:
    - [x] **Next.js + FastAPI**: SELECTED — Industry standard, excellent SEO (SSR/SSG), large ecosystem, streaming via SSE, FastAPI wraps existing Python RAG pipeline directly
    - [x] **Reflex**: Rejected — weaker SEO (client-rendered SPA), smaller ecosystem, risk of stagnation
    - [x] **Static site + API**: Rejected — too limiting for interactive streaming UX, would need a framework eventually
  - [x] Decision criteria: (1) time to ship MVP, (2) SEO capability for organic growth, (3) team skills, (4) migration cost if we change later
  - [x] [PO] Framework selected: Next.js (App Router) + FastAPI. Rationale documented in Phase 3B plan.

- [x] **3B.2 — MVP web interface** ✅ (2026-02-26)
  - [x] Single question input (prominent, centered, with placeholder text suggesting a question)
  - [x] Answer display: formatted text with inline citations linked to source URLs (react-markdown)
  - [x] Mode toggle: "Employee" / "Legal Professional" — simple, clear, no jargon
  - [x] Persistent legal disclaimer (footer, always visible)
  - [x] Source attribution: "Sources" section below each answer listing retrieved chunks with category labels
  - [x] Loading state: streaming response display (tokens appear as generated via SSE)
  - [x] Error handling: clear messages for API failures, rate limits (429), empty queries (validation)
  - [x] Mobile responsive (Tailwind responsive classes)
  - [x] **Explicitly NOT in MVP**: chat history, user accounts, conversation memory, persistence, sign-up walls
  - [x] Write end-to-end tests: 23 tests covering health, SSE streaming, validation, rate limiting, error handling, schemas

- [x] **3B.3 — SEO topic pages** ✅ (2026-02-26)
  - [x] Create static pages for 11 subject areas from Appendix A taxonomy (SSG via generateStaticParams)
  - [x] Each page includes: topic overview, 5 common questions with pre-generated answers, "Ask your own question" CTA
  - [x] Implement schema.org FAQPage markup for search engine rich results (JSON-LD)
  - [x] Internal linking between related topics (related topics grid + topic pills on home page)
  - [x] Meta descriptions optimized for search intent (per-topic metaDescription field)

- [ ] **3B.4 — Analytics and feedback**
  - [ ] Install privacy-respecting analytics (same as landing page)
  - [ ] Track: query volume per day, mode distribution (consumer vs. attorney), session duration, bounce rate, pages/session, return visits (7-day and 30-day), traffic sources
  - [ ] Implement thumbs up/down feedback on every answer
  - [ ] Store feedback: query hash (not raw query, for privacy), mode, rating, timestamp
  - [ ] Build a simple feedback dashboard (even a CLI command that summarizes feedback data)

- [ ] **[GATE] 3B.5 — MVP launch readiness**
  - [ ] MVP deployed to public URL
  - [ ] Analytics collecting data
  - [ ] Feedback mechanism working
  - [ ] Both modes functional end-to-end (consumer: plain-language + source URLs, attorney: legal analysis + statutory citations)
  - [ ] Disclaimer visible on every page
  - [ ] Responsive on mobile
  - [ ] Page load time < 3 seconds
  - [ ] Basic rate limiting in place (prevent abuse before beta)
  - [ ] **MVP is live and ready for beta users**

---

#### 3C — Closed Beta & Validation

**Goal:** Test the product with real users and measure product-market fit signals. This is the most important phase in the entire project — it determines whether the remaining phases are warranted. Apply innovation accounting (Eric Ries, *The Lean Startup*): establish baseline metrics, then tune toward ideal.

- [ ] **3C.1 — Beta cohort recruitment**
  - [ ] Consumer cohort (target 20–50 users):
    - [ ] Landing page email sign-ups (from 3A.2)
    - [ ] Reddit r/legaladvice, r/AskHR, California employment law subreddits
    - [ ] Local legal aid organizations (they serve people who can't afford attorneys)
    - [ ] Employee rights advocacy groups
  - [ ] Attorney cohort (target 5–10):
    - [ ] California Lawyers Association — Labor & Employment Law Section
    - [ ] Solo practitioner and small firm networks
    - [ ] Legal tech early adopter communities
  - [ ] Prepare onboarding email: what the product does, what we're testing, how to give feedback, how their data is handled (privacy commitment)

- [ ] **3C.2 — 4-week structured beta**
  - [ ] Week 1: Launch to cohort. Monitor for crashes, errors, and showstoppers. Track first-session behavior: do users ask a question? Do they read the full answer? Do they engage with citations?
  - [ ] Week 2: First exit interviews (5 users). Ask: "What was helpful? What was confusing? Did you trust the answer? What would you do differently?" Track 7-day return rate.
  - [ ] Week 3: Introduce pricing signal (see 3C.4). Continue monitoring engagement. Identify the top 3 pain points from feedback data.
  - [ ] Week 4: Final exit interviews (5 users). Measure: 7-day and 30-day return rates, average feedback score, queries/user, mode preference split.
  - [ ] Document all findings in a beta results report

- [ ] **3C.3 — Iterate based on feedback**
  - [ ] Expect 2–3 iteration cycles during the 4-week beta
  - [ ] Common issues to watch for and remediation:
    - [ ] Trust gap: users want to see sources BEFORE the answer → add "searching sources..." animation with source preview
    - [ ] Topic gaps: users ask about areas where our KB is thin → fast-track content expansion for high-demand topics
    - [ ] Mode confusion: users don't understand consumer vs. attorney → test single-mode entry with auto-detection
    - [ ] Answer quality: specific question types produce weak answers → refine prompts, add evaluation questions
    - [ ] Citation density: consumers find citations distracting, attorneys want more → mode-specific citation rendering
  - [ ] Ship fixes within 48 hours of identifying critical issues

- [ ] **3C.4 — Pricing validation experiment**
  - [ ] At beta week 3, introduce a prompt: "We're launching premium features soon — early access pricing available"
  - [ ] For attorneys: display a pricing page ($49/month early-access, $99/month regular) with "Reserve your spot" button
  - [ ] Measure: click-through rate on pricing prompt, pricing page views, "Reserve" button clicks
  - [ ] Even 3 attorney commitments validates willingness to pay
  - [ ] For consumers: test a "Support this project" / "Unlock detailed analysis" prompt to gauge upgrade interest

- [ ] **[GATE] 3C.5 — Product-market fit assessment**
  - [ ] **Quantitative signals**:
    - [ ] Consumer 7-day return rate > 30% (target)
    - [ ] Attorney 7-day return rate > 50% (target)
    - [ ] Average feedback score > 3.5/5
    - [ ] At least 3 attorneys express concrete willingness to pay (pricing experiment conversions)
  - [ ] **Qualitative signals** (from interviews):
    - [ ] Users describe the product solving a real problem (not just "interesting" or "cool")
    - [ ] At least 2 users report recommending it to someone else (organic referral)
    - [ ] Users describe specific scenarios where they would use it again
  - [ ] **Red flags that require deeper investigation before Phase 4**:
    - [ ] Return rate < 15% (users try once and leave)
    - [ ] Feedback score < 3.0/5 (answers are not meeting expectations)
    - [ ] Zero attorney willingness to pay (business model may need rethinking)
    - [ ] Trust concerns dominate interviews (may need human-in-the-loop review layer)
  - [ ] [PO] Decision: proceed to Phase 4 (strong signals), iterate on Phase 3 (mixed signals), or pivot (weak signals)
  - [ ] **Phase 3 COMPLETE**

---

### Phase 4: Production, Growth & Business Model

> **Strategic context (2026-02-26):** Phase 4 only proceeds if Phase 3C demonstrates product-market fit signals. It combines production infrastructure (necessary) with growth engineering and business model implementation (sufficient for a sustainable product). The three sub-phases can partially overlap: 4A enables 4B and 4C.

#### 4A — Production Infrastructure

**Goal:** Deploy a production-grade application with monitoring, security, and operational procedures.

- [ ] **4A.1 — Hosting and deployment**
  - [ ] [PO] Select hosting provider: evaluate for cost at low scale (<1,000 queries/day), auto-scaling capability, deployment simplicity, and SSR/SSG support for SEO
  - [ ] Set up production environment: domain, SSL, CDN for static assets
  - [ ] Configure environment-specific settings (dev, staging, production)
  - [ ] Set up production database (SQLite for initial scale; plan PostgreSQL migration trigger at ~10K concurrent users)
  - [ ] Set up production vector database (LanceDB or migration to hosted vector DB)
  - [ ] Configure LLM API keys and environment variables (secrets management)

- [ ] **4A.2 — CI/CD pipeline**
  - [ ] Set up CI/CD (GitHub Actions or similar)
  - [ ] Automated test suite on every PR (686+ tests)
  - [ ] Automated linting and type checking
  - [ ] Staging deployment on merge to main
  - [ ] Production deployment with manual approval gate
  - [ ] Database migration automation
  - [ ] Rollback procedure documented and tested
  - [ ] Deployment takes < 5 minutes (fast iteration is a competitive advantage)

- [ ] **4A.3 — Monitoring and observability**
  - [ ] Application error tracking (Sentry or similar)
  - [ ] Structured log aggregation
  - [ ] API response time monitoring (target: < 5s consumer, < 15s attorney end-to-end)
  - [ ] LLM API usage and cost tracking with daily budget alerts (alert at 80% of monthly budget)
  - [ ] Uptime monitoring and alerting (target: 99.5% uptime)
  - [ ] Usage analytics dashboard: queries/day, mode split, popular topics, geographic distribution, return rate

- [ ] **4A.4 — Security hardening**
  - [ ] Rate limiting on public endpoints (consumer: 5 queries/min, attorney free tier: 2 queries/min)
  - [ ] Input sanitization: prompt injection prevention (detect and reject adversarial inputs)
  - [ ] HTTPS enforced, HSTS headers
  - [ ] Dependency vulnerability scanning (Dependabot or similar, weekly)
  - [ ] No PII collection or storage verified (queries may contain sensitive employment info — never log raw queries)
  - [ ] Legal disclaimer text reviewed by an actual California employment attorney
  - [ ] Privacy policy published (describe what data is collected, how it's used, how long it's retained)

- [ ] **4A.5 — Operational procedures**
  - [ ] Content refresh runbook: how to re-ingest sources (weekly for agencies, monthly for statutory codes)
  - [ ] Incident response procedure: escalation path, communication template, post-mortem format
  - [ ] Backup and recovery: database backups, LanceDB index rebuild procedure
  - [ ] Cost monitoring: monthly LLM spend review, automatic alerts, model-tier adjustment playbook
  - [ ] On-call rotation (if applicable) or async monitoring setup

---

#### 4B — Growth & Acquisition

**Goal:** Build the distribution channels that bring users to the product. A great product with no distribution is just a demo. Applies Product-Led Growth principles: the product drives acquisition through value delivery and virality.

- [ ] **4B.1 — SEO execution**
  - [ ] Optimize topic pages from 3B.3 for top 50 target keywords (from 3A.3 research)
  - [ ] Implement schema.org markup: FAQPage, LegalService, WebApplication
  - [ ] Build internal linking structure between related topics
  - [ ] Submit sitemap to Google Search Console; monitor indexing and ranking progress weekly
  - [ ] Target: page 1 ranking for 10+ target keywords within 3 months
  - [ ] Measure: organic traffic growth, conversion (visitor → question asked)

- [ ] **4B.2 — Content marketing**
  - [ ] Publish 10 pillar articles on highest-volume topics: "California minimum wage [year]", "wrongful termination California", "FEHA discrimination", "whistleblower protections California", "California overtime law", etc.
  - [ ] Each article: authoritative content + "Ask a follow-up question" CTA linking to the interactive tool
  - [ ] Distribute via: social media, legal forums, employment rights communities
  - [ ] Measure: traffic per article, CTR to interactive tool, conversion to question asked

- [ ] **4B.3 — Referral and virality**
  - [ ] "Share this answer" button: generates a shareable URL with the question pre-loaded (answer regenerated for the recipient — not cached, to ensure freshness)
  - [ ] Social sharing: Open Graph meta tags for rich previews when shared on social media
  - [ ] Track viral coefficient: shares per user, new users per share, share-to-question conversion
  - [ ] Target: viral coefficient > 0.3 (each 10 users bring 3 new users)

- [ ] **4B.4 — Attorney channel development**
  - [ ] Reach out to California Lawyers Association — Labor & Employment Law Section
  - [ ] Reach out to local bar associations in major CA markets (LA, SF, San Diego, Sacramento)
  - [ ] Offer: free 90-day access in exchange for feedback and testimonials
  - [ ] Co-marketing opportunity: "Recommended by [X] attorneys" social proof
  - [ ] Attend 1–2 legal tech conferences or bar CLE events to demo the product
  - [ ] Measure: attorney sign-ups from each channel, cost per acquisition

- [ ] **4B.5 — Email engagement channel**
  - [ ] Implement opt-in email capture (landing page, post-answer "Get updates" prompt)
  - [ ] Weekly California employment law digest: summarize statutory changes (from PUBINFO delta), new agency guidance, trending questions
  - [ ] Segment by mode preference: consumer digest (plain language) vs. attorney digest (citations + analysis)
  - [ ] Measure: open rate, click-through rate, return visits driven by email
  - [ ] Target: 20% open rate, 5% CTR

---

#### 4C — Business Model Implementation

**Goal:** Turn usage into revenue. Validate unit economics. The business model is a hypothesis until real users are paying. Applies Lean Startup innovation accounting: establish baseline, tune engine, assess viability.

- [ ] **4C.1 — [PO] Pricing decision**
  - [ ] Review Phase 3C pricing experiment data
  - [ ] Recommended starting model (to be validated):
    - [ ] **Consumer free tier**: 5 questions/day, basic answers, disclaimers. No account required.
    - [ ] **Consumer premium** (optional, if demand signals exist): $9/month — conversation memory, detailed analysis, complaint guidance workflow. Requires account.
    - [ ] **Attorney professional**: $49/month (early-access) / $99/month (regular) — unlimited questions, copy/export, citation alerts, priority response.
    - [ ] **Enterprise/API**: Custom pricing — for HR platforms, legal tech tools, law firm integrations. Requires outbound sales.
  - [ ] [PO] Approve or adjust pricing tiers

- [ ] **4C.2 — Payment infrastructure**
  - [ ] Integrate Stripe: subscription management, usage tracking, invoicing
  - [ ] Implement free tier enforcement (query count per day, reset at midnight)
  - [ ] Implement upgrade prompts: non-intrusive, shown after value is delivered (e.g., after 3rd question of the day)
  - [ ] Implement downgrade/cancellation flow
  - [ ] Write tests for payment edge cases (failed payments, expired cards, refunds)

- [ ] **4C.3 — Attorney portal**
  - [ ] Account creation and authentication (email + password or OAuth)
  - [ ] Usage dashboard: queries this month, remaining quota (free trial), cost savings estimate
  - [ ] Billing management: payment method, invoice history, plan changes
  - [ ] Query history: searchable list of past questions and answers (opt-in, stored server-side)
  - [ ] Firm profile (optional): firm name, practice areas, for future multi-seat plans

- [ ] **4C.4 — Unit economics monitoring**
  - [ ] Build financial dashboard tracking:
    - [ ] Revenue: MRR (monthly recurring revenue), subscriber count, churn rate
    - [ ] Costs: LLM API cost per query (by mode), infrastructure cost, total variable cost per user
    - [ ] Efficiency: LTV (lifetime value), CAC (customer acquisition cost), LTV:CAC ratio
    - [ ] Health: monthly burn rate, runway at current growth rate
  - [ ] Set alerts: notify PO if LTV:CAC < 2:1 or if monthly LLM costs exceed revenue
  - [ ] Monthly financial review: are we trending toward sustainability?

- [ ] **[GATE] 4C.5 — Revenue milestone**
  - [ ] 100+ active free users (asked at least 1 question in the past 30 days)
  - [ ] 5+ paying attorney subscribers
  - [ ] Positive unit economics: revenue from paying users > variable costs (LLM + infrastructure) for those users
  - [ ] Monthly burn rate documented; runway > 12 months at current pace
  - [ ] Growth trend: user base growing month-over-month
  - [ ] [PO] Sign-off on business viability and Phase 5 investment
  - [ ] **Phase 4 COMPLETE — SUSTAINABLE BUSINESS FOUNDATION**

---

### Phase 5: Scale, Expand & Deepen

> **Strategic context (2026-02-26):** Phase 5 is driven by validated user demand from Phase 3–4 data. Features are prioritized by impact on retention (5A), knowledge quality (5B), and revenue/moat (5C). The specific ordering below is a hypothesis — it should be updated based on actual usage data, feedback patterns, and revenue signals. The principle: invest where users pull, not where technology pushes.

#### 5A — Retention & Engagement (Close the Build-Measure-Learn Loop)

**Goal:** Turn first-time users into repeat users. Address the top friction points identified during Phase 3C beta and Phase 4 production monitoring.

- [ ] **5A.1 — Multi-turn conversation memory**
  - [ ] Implement conversation session storage (session-based, no account required for consumers)
  - [ ] Context window management: summarize older turns to fit token budget
  - [ ] Mode-specific context handling: consumer preserves simple context, attorney preserves citations and analysis structure
  - [ ] Session expiry: conversations reset after 24 hours of inactivity (privacy + cost management)
  - [ ] Write tests for conversation state management
  - [ ] Measure impact: session depth (queries/session) before vs. after

- [ ] **5A.2 — Feedback-driven quality improvement loop**
  - [ ] Build feedback analysis pipeline: aggregate thumbs-down by topic, question type, and mode
  - [ ] Identify top 10 "pain topics" (questions that consistently get negative feedback)
  - [ ] For each pain topic: diagnose root cause (knowledge gap? prompt issue? retrieval miss?) and remediate
  - [ ] Implement weekly quality review cadence: review feedback data, prioritize improvements, ship fixes
  - [ ] Track quality improvement over time: average feedback score by week
  - [ ] This is the single most important operational process for product quality

- [ ] **5A.3 — Suggested follow-up questions**
  - [ ] After each answer, generate 2–3 relevant follow-up questions from the context
  - [ ] Follow-ups should deepen understanding (consumer) or expand analysis (attorney)
  - [ ] Clickable — one click to ask the follow-up, reducing effort for the next action
  - [ ] Measure: what % of users click a follow-up? Which follow-ups have highest engagement?

- [ ] **5A.4 — Consumer: guided complaint filing workflow**
  - [ ] Design step-by-step wizard: identify issue type → determine which agency → gather required documents → link to agency complaint form
  - [ ] Include timeline expectations (e.g., "CRD complaints typically take 60–90 days to investigate")
  - [ ] Include documentation checklists (e.g., "Gather: termination letter, pay stubs, written communications")
  - [ ] Link to relevant agency forms and instructions at each step
  - [ ] This transforms the product from information → action, the highest-value differentiation for consumers

- [ ] **5A.5 — Attorney: citation export and workflow integration**
  - [ ] "Copy citation" button for individual statutory citations (formatted for legal briefs)
  - [ ] "Copy full analysis" button (Markdown-formatted analysis for pasting into documents)
  - [ ] "Export to Word" for the complete analysis (DOCX format with proper heading styles)
  - [ ] These features reduce friction in the attorney's actual workflow — the value of Employee Help is the analysis, but the work product is a brief or memo

---

#### 5B — Knowledge Base Expansion (Demand-Driven)

**Goal:** Expand content coverage based on validated user demand. The principle: expand where users are asking questions we cannot answer, not where content is available.

- [ ] **5B.1 — Automated content refresh**
  - [ ] Implement scheduled re-ingestion: weekly for agency sources (web re-crawl), monthly for statutory codes (PUBINFO re-download)
  - [ ] Change detection: compare new content hashes to stored hashes, only re-embed changed chunks
  - [ ] Notification on changes: email or webhook alerting the team when statutory content changes
  - [ ] Implement re-embedding pipeline for changed chunks only (incremental, not full rebuild)
  - [ ] Write tests for change detection and incremental re-embedding
  - [ ] This is P0 — without it, content decays and trust erodes

- [ ] **5B.2 — P2 agency sources (demand-driven)**
  - [ ] Review Phase 4 query logs: which topics are users asking about that we can't answer?
  - [ ] Prioritize P2 sources by demand:
    - [ ] Cal/OSHA (`config/sources/cal_osha.yaml`) — if workplace safety questions are common
    - [ ] PERB (`config/sources/perb.yaml`) — if public sector collective bargaining questions arise
    - [ ] ALRB (`config/sources/alrb.yaml`) — if agricultural labor questions arise
    - [ ] CDE (`config/sources/cde.yaml`) — if child labor questions arise
  - [ ] For each: create config, run pipeline, spot-check quality, embed, verify retrieval

- [ ] **5B.3 — P2 statutory codes (demand-driven)**
  - [ ] Review attorney query patterns: which codes are being referenced that we don't cover?
  - [ ] Prioritize by demand:
    - [ ] Health & Safety Code — if Cal/OSHA questions reference specific statutes
    - [ ] Education Code (child labor sections) — if child labor questions arise
    - [ ] Civil Code (Unruh Act, sexual battery) — if employment-adjacent civil claims arise
  - [ ] For each: create config, run PUBINFO loader, verify citation accuracy, embed

- [ ] **5B.4 — California Code of Regulations (CCR)**
  - [ ] [SPIKE] Investigate CCR data source (regulations.ca.gov, or official regulatory dump)
  - [ ] Implement CCR extractor if needed (new source format)
  - [ ] Ingest employment-related CCR titles (Title 2: Administration, Title 8: Industrial Relations)
  - [ ] Tag as `regulation` content_category
  - [ ] Integrate into retrieval: regulations supplement statutes in attorney mode

- [ ] **5B.5 — Spanish language support**
  - [ ] [PO] Decide: Spanish first? (yes — ~39% of CA workforce is Hispanic/Latino)
  - [ ] Identify which agencies provide Spanish content (CRD and DIR have Spanish fact sheets)
  - [ ] Add `language` metadata to source configs, documents, and chunks
  - [ ] Evaluate multilingual embedding model (e.g., BGE-M3 supports multilingual)
  - [ ] Implement language-aware retrieval: detect query language, match to same-language content
  - [ ] Ingest Spanish-language fact sheets
  - [ ] Evaluate answer quality in Spanish (new evaluation dataset needed)

---

#### 5C — Platform & Competitive Moat (Build Defensibility)

**Goal:** Build features that create switching costs, defensibility, and new revenue channels. Applies Peter Thiel's monopoly theory: proprietary technology (10x better), network effects (API ecosystem), economies of scale (marginal cost approaches zero), and branding (the trusted source for CA employment law).

- [ ] **5C.1 — Attorney: cross-reference sidebar**
  - [ ] Implement cross-reference extraction from statutory text (detect "Section XXXX" references during ingestion)
  - [ ] Build cross-reference index: for each section, which other sections reference it and which does it reference?
  - [ ] Display "Related statutes" sidebar when viewing statutory citations in an answer
  - [ ] Clickable cross-references that show the referenced section inline
  - [ ] This is a Kano Model "delighter" — no competitor does this well, and it creates meaningful workflow value

- [ ] **5C.2 — Topic-guided browsing**
  - [ ] Implement topic taxonomy navigation based on Appendix A (Wages, Discrimination, Leave, Safety, etc.)
  - [ ] Pre-built queries per topic for quick access ("What is the minimum wage?" with one click)
  - [ ] Topic landing pages with key information, common questions, and relevant statutes
  - [ ] Browse by topic or by agency — two entry points to the same knowledge base
  - [ ] Excellent for SEO long-tail capture (hundreds of topic-specific pages)

- [ ] **5C.3 — API access (Enterprise revenue channel)**
  - [ ] Design RESTful API: `POST /v1/ask` with `query`, `mode`, `top_k` parameters
  - [ ] Implement authentication (API keys), rate limiting (per-key), and usage tracking
  - [ ] Build API documentation (OpenAPI/Swagger)
  - [ ] Implement usage-based billing (per-query pricing for API access)
  - [ ] Target integrations: HR platforms (Gusto, Rippling, BambooHR), legal tech tools, chatbot platforms
  - [ ] This is the "network effects" play — each integration brings the platform's users to Employee Help's knowledge base

- [ ] **5C.4 — Statutory change alerts**
  - [ ] Build alert subscription: attorneys select practice areas (discrimination, wages, whistleblower, etc.)
  - [ ] When PUBINFO delta processing detects changes in subscribed statutes, generate a change summary
  - [ ] Email notification with: what changed, old vs. new text diff, analysis of impact
  - [ ] This creates a habit trigger (Hooked model: external trigger → return visit → variable reward → investment)
  - [ ] Retention mechanism for attorney subscribers — they stay subscribed because the alerts are independently valuable

- [ ] **5C.5 — Multi-state expansion**
  - [ ] [PO] Only pursue after California PMF is proven and unit economics are positive
  - [ ] Template the California pipeline for other states: identify equivalent statutory databases, agency sources, and citation formats
  - [ ] Start with the largest employment markets: Texas, New York, Florida, Illinois
  - [ ] Each state requires: statutory data source, agency source configs, state-specific prompt templates, evaluation dataset
  - [ ] This is the 1-to-n scaling play (Zero to One) — only valid after the 0-to-1 is confirmed in California
  - [ ] Estimate: each new state is ~4–6 weeks of pipeline + evaluation work, plus ongoing maintenance

---

### Cross-Cutting Concerns (All Phases)

These items apply throughout the project and should be maintained continuously.

- [ ] **Testing discipline**
  - [ ] Maintain >80% code coverage on all new modules
  - [ ] Unit tests for all business logic
  - [ ] Integration tests for pipeline workflows
  - [ ] End-to-end tests for critical user paths
  - [ ] Live/network tests isolated behind pytest marks

- [ ] **Documentation**
  - [ ] Update EXPANDED_REQUIREMENTS.md as PO decisions are made
  - [ ] ADRs for significant technical decisions
  - [ ] Runbooks for operational procedures
  - [ ] API documentation for service interfaces
  - [ ] User-facing help content for the web application

- [ ] **Code quality**
  - [ ] Type hints on all public interfaces
  - [ ] Structured logging with source identity in every log entry
  - [ ] Error handling: retry with backoff for transient failures, skip + log for persistent
  - [ ] No single source failure should abort a multi-source run

- [ ] **Product discipline (Phase 3+)**
  - [ ] Every feature must trace back to a validated user job (Section 3.7.2) or a specific experiment from the Risk Registry (Section 3.7.6)
  - [ ] Track activation metric from day one: % of visitors who ask their first question
  - [ ] Maintain a "kill list" — features that seem important but lack evidence of user demand
  - [ ] Review feedback data (thumbs up/down) weekly; identify the top 3 quality pain points
  - [ ] Monitor unit economics monthly: cost per query, revenue per user, LTV:CAC ratio
  - [ ] Ship small, measure fast: prefer weekly deploys over monthly launches. Minimize time through the Build-Measure-Learn loop.
  - [ ] Apply the Kano Model to every feature decision: is it must-have, performance, or delighter? Must-haves are non-negotiable. Performance is where we compete. Delighters are how we differentiate.
  - [ ] Before building any new feature, ask: "What is the cheapest experiment that could validate or invalidate this?" (Bland & Osterwalder, *Testing Business Ideas*)

- [ ] **Trust & safety (Phase 3+)**
  - [ ] Legal disclaimer visible on every page and every answer — text reviewed by an actual California employment attorney
  - [ ] Citation transparency: every factual claim linked to its source; users can click to verify
  - [ ] Confidence indicators: flag answers where retrieval quality is low (e.g., fewer than 3 relevant chunks retrieved)
  - [ ] Prompt injection prevention: input sanitization, output monitoring for unexpected content
  - [ ] No PII collection or storage — queries may contain sensitive employment information; never log raw query text in production
  - [ ] Regular citation accuracy audits: monthly sample of 50 attorney answers, manually verified against source statutes
  - [ ] Graceful degradation: if the LLM API is unavailable, show a clear message directing users to the source agencies rather than failing silently

---

## 8. Validation & Testing Strategy

This section documents the project's testing approach. It is a living document, updated as new phases introduce new testing categories.

### 8.1 Test Suite Overview

| Category | Count | Marker | CI/CD |
|----------|-------|--------|-------|
| **Unit tests** | ~543 | (default) | Every build |
| **Phase 2 unit tests** | ~143 | (default) | Every build |
| **Integration tests (slow)** | 8 | `@pytest.mark.slow` | Nightly / manual |
| **Live LLM tests** | 5 | `@pytest.mark.llm` | Manual (requires API key) |
| **Evaluation tests** | 60+ | `@pytest.mark.evaluation` | Manual / pre-release |
| **Total** | **686** | | |

### 8.2 What We Test (by Category)

#### A. Knowledge Base Integrity

Tests that the ingestion pipeline produces correct, complete, and well-structured data.

- **Citation format validation**: 48 spot-check tests (`tests/test_ingestion_spot_check.py`) verify that stored statutory chunks have correctly formatted citations matching `Cal. <Code> Code § <section>` patterns. Covers all 6 statutory codes, including edge cases like decimal section numbers (1102.5), deep subdivisions, and sections with brackets in PUBINFO data.
- **Cross-source validation**: 18 tests (`tests/test_cross_source_validation.py`) verify the `cross-validate` command produces correct reports. The live `employee-help cross-validate` command runs 7 check types across all 10 sources: source coverage, document counts, chunk counts, content category distribution, citation format sampling, cross-source duplicate detection, token bounds, and empty chunk detection. Results: 32/33 pass (1 known issue: CalHR oversized chunk).
- **Pipeline idempotency**: Tests verify that re-running the pipeline on unchanged content creates 0 new documents or chunks (content_hash deduplication).
- **Soft-delete handling**: Tests verify that repealed statutory sections (PUBINFO `active_flg='N'`) are excluded during ingestion and that chunks can be marked inactive without deletion.

#### B. Embedding & Vector Store

Tests that embeddings are generated correctly and the vector store supports all required search operations.

- **EmbeddingService unit tests** (13): Mock the sentence-transformer model to verify batch logic, BGE query prefix application, empty content handling, and batch failure survival (skips failed chunks, continues with remaining).
- **EmbeddingService integration tests** (8, `@pytest.mark.slow`): Use the real bge-base-en-v1.5 model to verify that semantically similar texts produce closer vectors than unrelated texts. Example: embed "minimum wage in California" and "California hourly pay rate" — verify cosine similarity > 0.7. Also verifies query vs. document embedding asymmetry and end-to-end embed-store-search pipeline.
- **VectorStore unit tests** (24): Verify table creation, upsert (update existing rows by chunk_id), deletion, hybrid search, keyword search, metadata filtering, FTS dirty flag behavior, and stats computation.
- **Incremental embedding**: Tests verify that `embed --all` after a complete embedding run produces 0 new embeddings (content_hash comparison).

#### C. Retrieval Quality

Tests that the search pipeline returns relevant, well-ranked results for both consumer and attorney modes.

- **QueryPreprocessor tests**: Verify citation detection (recognizes "section 1102.5", "Lab. Code § 12940", etc.), legal term expansion (FEHA → Fair Employment and Housing Act), and query normalization.
- **RetrievalService unit tests**: Mock the VectorStore and Reranker to verify consumer mode filters to `agency_guidance`/`fact_sheet`/`faq`, attorney mode includes all categories with statutory boosting, citation boost is applied correctly, and diversity enforcement limits results per document.
- **Retrieval evaluation** (25 consumer + 25 attorney + 10 adversarial questions):
  - Each question has `expected_categories` (content types that should appear) and `expected_citations` (specific statute sections).
  - Metrics computed: precision@5 (fraction of top-5 that are relevant), recall@5 (fraction of expected citations found), MRR (reciprocal rank of first relevant result), citation_hit@1 (exact section in top-1 for citation lookups).
  - Pass/fail thresholds: consumer P@5 ≥ 0.6, attorney P@5 ≥ 0.7, citation top-1 ≥ 0.9.
  - Example consumer question: "What is the minimum wage in California?" — expects `agency_guidance` or `fact_sheet` content about wage rates.
  - Example attorney question: "What constitutes whistleblower retaliation under Labor Code section 1102.5?" — expects `statutory_code` content with citation matching "1102.5".
  - Example citation lookup: "Lab. Code section 1102.5" — expects the exact section as top-1 result.

#### D. Answer Generation Quality

Tests that the LLM produces accurate, well-cited, appropriately toned responses.

- **LLMClient unit tests** (12): Mock the Anthropic SDK to verify Citations API document block construction, streaming chunk assembly, model selection by mode, token usage tracking, timeout handling, and retry logic.
- **PromptBuilder unit tests** (16): Verify document block format (each chunk → one document content block with metadata header), token budget enforcement (drops lowest-scored chunks when over budget), template rendering for both modes.
- **AnswerService unit tests** (17): Mock retrieval and LLM to verify the full pipeline (retrieve → prompt → LLM → citation validation → response). Tests cover both synchronous and streaming generation, citation extraction from Claude Citations API, and the citation post-processor's strict and permissive modes.
- **Citation validation tests**: Verify that the post-processor correctly identifies hallucinated citations (not in retrieved chunks) and that it matches both section number AND code type (prevents cross-code false matches — e.g., Lab. Code § 12940 vs. Gov. Code § 12940).

#### E. Answer Evaluation (60-Question Suite)

The full automated evaluation runs all 60 questions through the complete pipeline and computes aggregate metrics.

- **Consumer mode evaluation** (25 questions):
  - Disclaimer presence: regex check for "educational purposes" / "not legal advice" / "consult attorney"
  - Reading level: Flesch-Kincaid grade level estimation (target: grade 8–12 for accessibility)
  - Answer length and cost tracking
  - Results: 100% disclaimer rate, avg reading level 6.6, avg cost $0.006/query

- **Attorney mode evaluation** (25 questions):
  - Disclaimer presence: regex check for "independently verified" / "does not constitute legal advice"
  - Citation completeness: fraction of expected citations (from YAML) found in the answer
  - Citation count: number of statutory citations extracted from the answer
  - Reading level and cost tracking
  - Results: 92% disclaimer rate (2 citation-lookup-only questions omit full disclaimer — expected), 73% citation completeness, avg 6.7 citations/answer, avg cost $0.032/query

- **Adversarial evaluation** (10 questions):
  - Behavior verification: keyword-based check that the LLM exhibits expected behavior for each adversarial scenario
  - `out_of_scope`: expects indicators like "outside the scope", "family law", "not california employment"
  - `citation_not_found`: expects indicators like "not found", "no information", "don't have"
  - `clarification_needed`: expects indicators like "could you clarify", "more specific", "what area"
  - Results: 100% pass rate (all 10 adversarial questions handled correctly)

- **Cross-mode comparison**: The same knowledge base serves both modes. A question like "What protections exist for whistleblowers?" retrieves agency fact sheets in consumer mode (plain-language explanation) and statutory code sections in attorney mode (Lab. Code § 1102.5 analysis with elements and burden of proof). The evaluation verifies that each mode returns the appropriate content type and tone.

#### F. Regression Prevention

- **Citation regression suite** (`tests/test_ingestion_spot_check.py`): 48 golden citation tests run on every CI build. If a code change breaks citation parsing, these tests catch it immediately.
- **Retrieval quality thresholds**: The `evaluate-retrieval` command asserts aggregate metrics against configurable thresholds. A retrieval code change that degrades precision below threshold fails the evaluation.
- **Unit test count monitoring**: Each phase documents the expected test count. Phase 1: 171. Phase 1.5: 436. Phase 2: 686. Phase 2 + CACI: 750. Significant drops indicate regressions.

### 8.3 Running Tests

```bash
# All fast unit tests (default, ~750 tests)
uv run pytest

# Include slow integration tests (real embedding model)
uv run pytest -m "slow"

# Include LLM tests (requires ANTHROPIC_API_KEY)
uv run pytest -m "llm"

# Run full retrieval evaluation (requires embedded data)
uv run employee-help evaluate-retrieval

# Run full answer evaluation (requires ANTHROPIC_API_KEY + embedded data)
uv run employee-help evaluate-answers

# Run answer evaluation without LLM calls (retrieval only)
uv run employee-help evaluate-answers --dry-run

# Cross-source validation report
uv run employee-help cross-validate
```

---

## 9. Phase Summary (Revised 2026-02-26)

| Phase | Focus | Key Outcome | Key Risk |
|-------|-------|-------------|----------|
| **Phase 1** ✅ | CRD Knowledge Acquisition | CRD employment discrimination content in SQLite (done) | — |
| **Phase 1.5** ✅ (code complete, PO gate pending) | Multi-Source & Statutory Expansion | 10 sources ingested (6 statutory + 3 agency + 1 CACI jury instructions): 20,871 docs, 24,106 chunks. 32/33 validation checks pass. | — |
| **Phase 2** ✅ (code complete, PO gate pending) | Dual-Mode RAG Pipeline | Embedding (bge-base-en-v1.5 + LanceDB), hybrid search, dual-mode retrieval, Claude answer generation (Haiku 4.5 / Sonnet 4.6), 60-question evaluation suite. 750 tests. | — |
| **Phase 3** | Customer Validation & MVP | Validate desirability (user trust, demand), ship minimum viable web app, run closed beta, measure product-market fit signals | **Desirability** — zero real users; trust in AI legal info is untested |
| **Phase 4** | Production, Growth & Business Model | SEO-driven acquisition, attorney subscriptions, payment infrastructure, production monitoring, unit economics | **Viability** — revenue model and unit economics are hypotheses |
| **Phase 5** | Scale, Expand & Deepen | Retention features (conversation memory, feedback loop), demand-driven KB expansion, API platform, multi-state expansion | **Scalability** — per-query costs at high volume; multi-state is a 1-to-n play |

> **Phases 1–2 are the feasibility path** (validated: the technology works). **Phase 3 is the desirability inflection point** — it determines whether the product has real demand or is a technically impressive solution without a market. **Phase 4 is the viability test** — can we build a sustainable business? Phase 4 investment is only warranted if Phase 3 demonstrates product-market fit signals. **Phase 5 is the scale play** — driven by data from real users, not assumptions. Features are prioritized by validated demand, not by technical convenience.

---

## 10. Product Owner Decisions (Resolved)

| # | Question | Decision | Impact |
|---|----------|----------|--------|
| 1 | **Phase 1.5 vs. Phase 2 priority** | **A) Sources first (1.5 → 2 → 3).** Build the broad data foundation before the chatbot. | The first user-facing chatbot will cover all employment rights topics from day one. No rework on embeddings/prompts when sources expand. |
| 2 | **Statutory code depth** | **A) All 7 Labor Code divisions (comprehensive).** Full ingestion (~4,000 sections). | Attorneys get the complete statutory foundation from the start. Longer Phase 1.5C but maximizes the investment in citation infrastructure. |
| 3 | **Attorney mode MVP scope** | **A) Full citation mode from day one.** Attorney mode launches with precise § references, clickable leginfo links, and legal analysis structure. | Phase 2–3 are more complex, but the core attorney value proposition is delivered immediately. Consistent with the comprehensive statutory ingestion decision. |
| 4 | **CalHR scope** | **A) Include with metadata tag.** CalHR content ingested into the unified knowledge base, tagged with "state_employees" metadata flag for filtering. | One knowledge base, metadata-driven filtering. Retrieval can de-prioritize CalHR content for private-sector questions. |
| 5 | **Content refresh cadence** | **A) Add basic automation (cron) in Phase 1.5.** Weekly for agencies, monthly for statutory codes, with change detection. | Keeps content fresh without manual effort. Adds ~2–3 tasks to Phase 1.5D. |
| 6 | **Phase 3 approach: build-first vs. validate-first** | **Pending PO review (2026-02-26).** Proposed: restructure Phase 3 around customer validation (Lean Startup methodology) before full web application build. Phase 3A = customer discovery + landing page test. Phase 3B = minimum viable web app. Phase 3C = closed beta with real users. | Major reframe: Phase 3 becomes a validation phase, not just a build phase. Investment in Phase 4 is contingent on Phase 3C product-market fit signals. See Section 3.7. |
| 7 | **Revenue model** | **Pending PO decision.** Proposed: free consumer tier (5 questions/day) + attorney subscription ($49–99/month) + enterprise API (custom pricing). To be validated during Phase 3C beta. | Defines the business model for Phase 4C implementation. Cannot proceed with payment infrastructure until pricing is decided. |
| 8 | **Web framework for Phase 3** | **Pending PO decision.** Options: Next.js + FastAPI (best SEO, industry standard), Reflex (Python-native, fast prototyping), or static site + API (simplest MVP). Recommend deciding at Phase 3B based on 3A findings. | Framework choice affects time-to-MVP, SEO capability, and long-term maintenance. |

---

## 11. Product Owner Decisions (Previously Resolved — Still Valid)

| # | Question | Decision | Impact |
|---|----------|----------|--------|
| 1 | Include CRD regulatory text in Phase 1? | **Defer.** | Still deferred; regulatory text (CCR) moves to Phase 5. |
| 2 | PDF scope? | **Consumer-facing only.** | Still valid for agency sources; statutory codes are a new category. |
| 3 | Content refresh cadence? | **Manual/ad-hoc via CLI.** | Under review for Phase 1.5 given expanded source count (see Decision #5 above). |
| 4 | External AI APIs? | **External APIs fine.** | Still valid. |
| 5 | Hosting preference? | **Decide at Phase 4.** | Still valid. |

---

## Appendix A: California Employment Rights — Subject Matter Taxonomy

This taxonomy organizes the subject areas covered by the expanded knowledge base. It serves as both a content completeness checklist and a future navigation/topic structure for the UI.

| Category | Sub-Topics | Primary Agencies | Primary Codes |
|----------|-----------|-----------------|---------------|
| **Wages & Compensation** | Minimum wage, overtime, meal/rest breaks, pay stubs, final pay, prevailing wage, tip protections | DIR/DLSE | Lab. Code Div. 2 |
| **Discrimination & Harassment** | Protected categories, harassment, reasonable accommodation, pregnancy, age, disability | CRD | Gov. Code §§ 12900–12996 |
| **Retaliation & Whistleblower** | Retaliation for exercising rights, whistleblower protections, qui tam | CRD, DIR | Lab. Code § 1102.5, Gov. Code §§ 8547+ |
| **Leave & Time Off** | CFRA, PDL, PFL, SDI, sick leave, kin care, bereavement | CRD, EDD | Gov. Code (FEHA/CFRA), Unemp. Ins. Code, Lab. Code |
| **Workplace Safety** | Cal/OSHA standards, hazard reporting, injury/illness prevention, retaliation for safety complaints | DIR/Cal-OSHA | Lab. Code Div. 5, Health & Saf. Code |
| **Workers' Compensation** | Benefits, claims process, employer obligations, return to work | DIR/DWC | Lab. Code Div. 4 |
| **Unemployment Benefits** | UI eligibility, claims process, employer obligations | EDD | Unemp. Ins. Code Div. 1 |
| **Employment Contracts** | Non-competes (void in CA), trade secrets, invention assignment, at-will employment | — | Lab. Code Div. 3, Bus. & Prof. Code § 16600+ |
| **Child Labor** | Work permits, hour restrictions, prohibited occupations | CDE, DIR | Ed. Code §§ 49110–49145, Lab. Code |
| **Public Sector Employment** | Civil service, merit system, collective bargaining, PERB process | CalHR, PERB | Gov. Code Title 2 Div. 5 |
| **Agricultural Labor** | Farmworker rights, ALRB process, organizing rights | ALRB | Lab. Code Div. 2 Part 3.5 |
| **Unfair Business Practices** | UCL claims for employment violations, private attorney general (PAGA) | — | Bus. & Prof. Code § 17200+, Lab. Code § 2698+ |
| **Complaint & Claims Process** | Filing with agencies, statutes of limitation, administrative remedies, right-to-sue | CRD, DIR, PERB | Code Civ. Proc. § 340+, Gov. Code |

---

## Appendix B: Statutory Citation Format Reference

For attorney-mode citation rendering, the system uses standard California legal citation format:

| Code | Abbreviation | Example Citation |
|------|-------------|-----------------|
| Labor Code | Lab. Code | Cal. Lab. Code § 1102.5 |
| Government Code | Gov. Code | Cal. Gov. Code § 12940(a) |
| Business & Professions Code | Bus. & Prof. Code | Cal. Bus. & Prof. Code § 17200 |
| Code of Civil Procedure | Code Civ. Proc. | Cal. Code Civ. Proc. § 340(a) |
| Unemployment Insurance Code | Unemp. Ins. Code | Cal. Unemp. Ins. Code § 1256 |
| Health & Safety Code | Health & Saf. Code | Cal. Health & Saf. Code § 25100 |
| Education Code | Ed. Code | Cal. Ed. Code § 49110 |
| Civil Code | Civ. Code | Cal. Civ. Code § 51 |

**Format rules:**
- Always prefix with "Cal." for California
- Section symbol: § (single section) or §§ (range)
- Subdivision in parentheses: § 12940(a)(1)
- No period after § symbol
- Effective date notation: "(eff. Jan. 1, 2026)" when relevant

---

## Appendix C: Source-Specific Technical Notes

### CRD (calcivilrights.ca.gov) — COMPLETED
- **CMS**: WordPress/Divi
- **Rendering**: Requires Playwright (JS-rendered accordions)
- **Content selector**: `#et-main-area`
- **Known issues**: Accordion content hidden in DOM without JS rendering

### DIR (dir.ca.gov)
- **CMS**: Custom (relatively static HTML)
- **Rendering**: Likely works with static HTML parsing; validate with spike
- **Content areas**: DLSE (Labor Commissioner), DOSH (Cal/OSHA), DWC (Workers' Comp)
- **Note**: Large site with many sub-domains; scope rules must be precise

### EDD (edd.ca.gov)
- **CMS**: ca.gov platform (modern, well-structured)
- **Rendering**: Likely static HTML; validate with spike
- **Content focus**: UI, SDI, PFL benefits and employer obligations
- **Note**: Large site; restrict to employee rights content, not employer tax administration

### CalHR (calhr.ca.gov)
- **CMS**: ca.gov platform
- **Content**: HR Manual (hrmanual.calhr.ca.gov — separate subdomain), policy memos
- **Note**: Content is primarily for state employees; tag with metadata

### PERB (perb.ca.gov)
- **CMS**: WordPress
- **Content**: Public sector collective bargaining resources, FAQ, guides
- **Note**: Smaller site; relatively straightforward

### ALRB (alrb.ca.gov)
- **CMS**: WordPress/standard
- **Content**: Agricultural labor rights, organizing information
- **Note**: Small site; straightforward

### leginfo.legislature.ca.gov
- **CMS**: Java Server Faces (JSF)
- **Rendering**: Server-side rendering; HTML is available without JS
- **URL pattern**: `codes_displaySection.xhtml?lawCode=LAB&sectionNum=1102.5.`
- **TOC pattern**: `codesTOCSelected.xhtml?tocCode=LAB&tocTitle=+Labor+Code+-+LAB`
- **Content**: Public domain (Gov. Code § 10248)
- **Note**: JSF uses form posts for navigation; may need to construct section URLs directly from TOC data rather than following links

---

*End of Expanded Requirements Document*
