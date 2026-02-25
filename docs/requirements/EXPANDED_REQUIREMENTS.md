# Employee Help — Expanded Requirements: Multi-Source Knowledge Acquisition & Dual-Mode Legal Guidance

> **Project:** Employee Help — AI-Powered Legal Guidance Platform
> **Author:** Claude (Opus 4.6) for Product Owner review
> **Date:** 2026-02-25
> **Status:** APPROVED — All PO decisions resolved (2026-02-25)
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
| **Estimated volume** | ~50 pages, ~500 chunks | ~5,000–10,000 pages, ~50,000–100,000 chunks |

---

### Pressure-Test: Assumptions Examined

#### Assumption 1: "We can treat all government websites the same way"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Each California agency website is built on a different CMS and tech stack. CRD uses WordPress/Divi (JS-rendered). DIR uses a custom CMS with relatively static HTML. EDD is a large modern site (ca.gov platform). PERB is a simpler WordPress site. leginfo.legislature.ca.gov uses Java Server Faces (JSF) — a server-side framework that renders HTML on the server but uses URL parameters and form posts for navigation, not clean REST URLs. A one-size-fits-all crawler will fail on at least half of these sites. |
| **Resolution** | Adopt a **source-registry architecture** where each agency is defined as a configuration entry with its own seed URLs, scope rules, extraction hints, and rate limits. The crawler core stays the same (Playwright + BeautifulSoup), but each source can specify custom CSS selectors for content areas, boilerplate patterns, and URL normalization rules. For leginfo specifically, we will need a **specialized statutory code extractor** because its content hierarchy (Division > Part > Chapter > Article > Section) is semantically different from free-form guidance pages. |

#### Assumption 2: "We can just add more seed URLs to the existing config"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The current `scraper.yaml` is a flat file with one set of seed URLs, one allowlist, and one blocklist. Adding 8 agencies' worth of patterns into one file creates a maintenance nightmare. Worse, a single misconfigured blocklist pattern for DIR could accidentally filter out CRD content. Each source also has different operational characteristics — EDD may tolerate faster crawling than PERB. |
| **Resolution** | Restructure configuration into a **source registry** model: one top-level config that references individual source definition files (or sections). Each source carries its own identity, scope rules, rate limits, and extraction parameters. The pipeline iterates over registered sources, running each as an independent crawl job with its own run record. Shared defaults minimize repetition. |

#### Assumption 3: "Statutory code is just more HTML to scrape"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | Statutory code is fundamentally different from agency guidance. A fact sheet explains what the law means in plain language. A code section *is* the law. The data model, chunking strategy, citation format, and retrieval strategy all differ. A code section like Labor Code § 1102.5 has a precise canonical citation, an effective date, subdivision structure (a)(1)(A), and may cross-reference other sections. Chunking a statute the same way we chunk a web page destroys the structural integrity that makes legal citation possible. |
| **Technical Architect** | The leginfo website (leginfo.legislature.ca.gov) organizes codes hierarchically: Code → Division → Part → Chapter → Article → Section. Each section has a stable URL pattern. The content is public domain (Gov. Code § 10248), so there are no legal barriers to ingestion. However, the JSF-based navigation means URL patterns contain view state parameters. We need to navigate the table-of-contents tree programmatically rather than following HTML links. |
| **Resolution** | Create a **dedicated statutory code pipeline** that understands legal hierarchy. Code sections are stored with full citation metadata (code name, section number, subdivision, effective date). Chunking respects section boundaries — a single code section is one chunk (or, if unusually long, split at subdivision boundaries while preserving the section citation context). The data model adds a `citation` field and a `content_category` enum that distinguishes `statutory_code` from `agency_guidance`. |

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

#### Assumption 6: "Scale from 500 to 100,000 chunks doesn't change the architecture"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Phase 1 stores ~500 chunks in SQLite with keyword search. At 50,000–100,000 chunks, SQLite remains viable for storage (it handles millions of rows well), but **retrieval quality** becomes the bottleneck. Vector similarity search across 100K chunks needs a proper vector index — NumPy cosine similarity over a flat array won't scale to acceptable latency. Keyword search alone won't surface the right statutory sections for a nuanced legal question. |
| **Software Architect** | The Phase 2 embedding/search decision (currently deferred) becomes more consequential at this scale. ChromaDB or Qdrant can handle 100K vectors easily, but the choice affects deployment complexity and cost. |
| **Resolution** | The expanded requirements don't change the Phase 1 or Phase 2 architecture *decisions* — they change the *parameters*. SQLite remains correct for storage. The Phase 2 vector search evaluation (task 2A.1) now explicitly considers 100K-chunk scale as a sizing requirement. The chunking pipeline adds content-category metadata so that retrieval can filter by type (statutory vs. guidance) before similarity search, which improves precision and reduces the effective search space. |

#### Assumption 7: "Adding sources is a one-time effort"

| Lens | Challenge |
|------|-----------|
| **Product Manager** | California laws change annually (effective January 1). Agency guidance pages get updated throughout the year. New agencies may be added. The system must support **ongoing source management** — adding new agencies, updating code sections when laws change, handling amended or repealed statutes. This is an operational concern, not just a build-time concern. |
| **Resolution** | Design the source registry and pipeline so that **adding a new agency source is a configuration change**, not a code change. The CLI `scrape` command accepts a `--source` parameter to run a specific source, or runs all sources if omitted. The statutory code pipeline tracks the "as of" date for each code section and can detect changes on re-run. Repealed sections are soft-deleted (marked as inactive, not removed) to prevent broken references. |

#### Assumption 8: "Attorney-grade citation accuracy is a Phase 5 polish item"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | If we build the knowledge base without citation-ready metadata from the start, retrofitting it later means re-ingesting all statutory content with a different schema. Citation accuracy isn't a UI feature — it's a **data architecture requirement** that must be embedded in the ingestion pipeline. An attorney who sees "Cal. Lab. Code § 1102" when the actual section is "§ 1102.5" will never trust the tool again. |
| **Resolution** | The statutory code extraction pipeline must capture **section-level citation metadata** from day one: code abbreviation, section number (with decimal subdivisions like 1102.5), subdivision markers, and the full canonical citation string. This metadata is stored alongside the chunk content and is available for any retrieval mode. The attorney-facing experience is a later phase, but the data foundation is built during ingestion. |

---

### Key Risks (Expanded)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Citation inaccuracy in attorney mode** | Critical | Section-level metadata captured at ingestion; citation format validated against known patterns; human review of citation samples |
| **Stale statutory content after annual law changes** | Critical | Track effective dates; support re-ingestion with change detection; flag chunks from amended sections |
| **Government website structural changes break crawlers** | High | Source-specific extraction config isolates blast radius; monitoring alerts on crawl failures; per-source health checks |
| **Retrieval quality degrades at 100K chunk scale** | High | Content-category filtering before vector search; hybrid search (semantic + metadata); evaluation benchmark suite |
| **Scope creep across 29 California codes** | Medium | Curated code manifest with PO approval; new codes require explicit addition |
| **Consumer receives attorney-level complexity (or vice versa)** | Medium | Separate retrieval strategies and prompt templates per mode; mode selection is explicit, not inferred |
| **leginfo JSF navigation defeats standard crawling** | Medium | Specialized statutory extractor with table-of-contents traversal; fallback to structured URL generation from known code hierarchy |
| **Inconsistent content quality across agencies** | Medium | Per-source quality validation; cleaner rules customizable per source; manual QA on first ingestion of each source |

---

## 1. Vision & Context (Expanded)

### 1.1 Product Vision (Revised)

Build an AI-powered legal guidance platform that helps **California employees understand their workplace rights** and helps **attorneys research California employment law** — drawing from a comprehensive, multi-source knowledge base of official government publications and statutory authority.

The platform serves two distinct user personas:

- **Employee/Consumer Mode**: Plain-language guidance for workers with questions about wages, discrimination, leave, safety, retaliation, unemployment benefits, and other employment rights. Answers cite government agency sources by URL. Tone: reassuring, clear, actionable.

- **Attorney/Professional Mode**: Statutory analysis with precise legal citations for practitioners researching California employment law. Answers cite code sections with subdivision precision, cross-reference related statutes, and distinguish between statutory text and agency interpretation. Tone: precise, authoritative, well-sourced.

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

Statutory codes are ingested from the California Legislative Information website (leginfo.legislature.ca.gov). Content is public domain per Government Code § 10248.

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
                       | "regulation" | "poster" | "faq"

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

  crawl:
    rate_limit_seconds: 3.0  # More conservative for legislative site
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
        ├── For each STATUTORY CODE source:
        │       │
        │   [2. Configure]   →  Load code manifest (codes, divisions, sections)
        │       │
        │   [3. Navigate]    →  Traverse leginfo TOC tree for target code
        │       │
        │   [4. Extract]     →  Extract section text with citation metadata
        │       │
        │   [5. Parse]       →  Parse section number, subdivision structure
        │       │
        │   [6. Chunk]       →  Section-boundary chunking (1 section ≈ 1 chunk)
        │       │
        │   [7. Store]       →  Upsert with citation metadata + content_category
        │       │
        │   [8. Report]      →  Per-code run manifest
        │
        └── [9. Aggregate]   →  Cross-source summary report
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
| F-SC.2 | The statutory extractor shall navigate the leginfo.legislature.ca.gov table-of-contents hierarchy to discover all sections within the specified divisions. | Statutory content is hierarchically organized; flat crawling won't capture the structure. |
| F-SC.3 | Each extracted code section shall carry **citation metadata**: code name, code abbreviation, section number (including decimal subdivisions like "1102.5"), subdivision markers, division/part/chapter/article path, and the full canonical citation string. | Attorney-grade citation accuracy requires section-level metadata from ingestion (Pressure Test #8). |
| F-SC.4 | Code sections shall be chunked at **section boundaries** — one section per chunk where feasible. Unusually long sections may be split at subdivision boundaries while preserving the section citation on each resulting chunk. | Legal citation requires knowing exactly which section a chunk comes from. Splitting mid-section destroys citation integrity. |
| F-SC.5 | The statutory pipeline shall track the **effective date** or "as of" date for each ingested code section. | Laws change annually; users and attorneys need to know which version they're reading. |
| F-SC.6 | On re-ingestion, amended code sections shall be updated (new content hash), and repealed sections shall be marked as **inactive** rather than deleted. | Preserves referential integrity; allows future "historical" queries. |

### 4.4 Content Categorization

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-CC.1 | Every stored document and chunk shall carry a **content_category** label: `agency_guidance`, `fact_sheet`, `statutory_code`, `regulation`, `poster`, or `faq`. | Enables mode-specific retrieval filtering (consumer mode filters to guidance; attorney mode includes statutes). |
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
| NF-1 | Polite crawling per source: configurable rate limiting (default 2s for agencies, 3s for leginfo). | Responsible use of government websites. |
| NF-2 | Full pipeline for a single agency source shall complete within **30 minutes**. Full statutory code ingestion within **2 hours**. | Developer experience; operational feasibility. Large statutory codes have thousands of sections. |
| NF-3 | All source configurations externalized in **YAML files** in `config/sources/`. | Adding a new source is a file addition, not a code change. |
| NF-4 | Structured logging with **source identity** in every log entry. | Debugging and monitoring across multiple sources. |
| NF-5 | Test suite coverage >80% on core modules. | Quality assurance across expanded codebase. |
| NF-6 | The system shall handle **network failures gracefully** — retry with backoff for transient errors, skip and log for persistent failures, never abort an entire multi-source run due to one source's failure. | Resilience across multiple external dependencies. |

---

## 6. Expanded Roadmap

### Phase 1: Knowledge Acquisition — CRD (COMPLETED ✅)

Status: **Done.** 171 tests, 81% coverage. CRD employment discrimination content acquired and stored.

### Phase 1.5: Multi-Source Foundation & Statutory Ingestion (NEW)

> **Purpose:** Extend the Phase 1 pipeline to support multiple agency sources and statutory code ingestion. This is the data foundation for the dual-mode experience.

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

### Phase 2: RAG Pipeline & Answer Generation (Revised)

#### 2A — Embedding & Semantic Search (Revised for Scale)

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 2A.1 | Evaluate embedding model and vector search approach at **50K–100K chunk scale**. Must support metadata filtering (content_category, source_id) for mode-specific retrieval. Candidates: ChromaDB, Qdrant, pgvector (if migrating to PostgreSQL). | Phase 1.5 | ADR with scale benchmarks |
| 2A.2 | Implement embedding generation with **content-category-aware batching**: generate embeddings for all chunks; store vectors with metadata for filtering. | 2A.1 | Embedding pipeline |
| 2A.3 | Implement **dual-mode retrieval**: consumer mode retrieves from `agency_guidance` + `fact_sheet` + `faq` categories; attorney mode retrieves from all categories with `statutory_code` boosted. Both modes support hybrid search (semantic + keyword for citation lookup). | 2A.2 | Dual retrieval service |
| 2A.4 | **[GATE]** Search benchmark: 20+ consumer questions and 20+ attorney questions evaluated for recall and precision. Attorney mode must return the correct statutory section in top-5 results for citation-specific queries. | 2A.3 | Search quality validated |

#### 2B — LLM Integration & Dual-Mode Answer Generation (Revised)

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 2B.1 | Design **two prompt templates**: consumer mode (plain language, source URLs, reassuring tone, actionable next steps) and attorney mode (legal analysis structure, statutory citations with § precision, cross-references, element-by-element analysis). Both include appropriate disclaimers. | 2A.4 | Prompt templates |
| 2B.2 | Implement RAG answer generation service with **mode parameter**: accepts user query + mode → retrieves mode-appropriate chunks → assembles mode-appropriate prompt → calls LLM → formats response with mode-appropriate citations. | 2B.1, 2A.4 | Dual-mode RAG service |
| 2B.3 | Quality evaluation: 20+ consumer Q&A pairs + 20+ attorney Q&A pairs manually graded for accuracy, citation correctness (attorney mode), appropriate tone, and disclaimer presence. | 2B.2 | Evaluation report |
| 2B.4 | **[GATE]** Both modes produce accurate, well-sourced, appropriately toned responses. Attorney mode citations verified against leginfo. | 2B.1–2B.3 | Validated dual-mode RAG |

### Phase 3: Web Application (Revised for Dual Mode)

#### 3A — Application Shell

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3A.1 | Initialize Reflex project; implement state class wrapping dual-mode RAG service. | 2B.4 | Reflex app skeleton |
| 3A.2 | Design layout with **mode selector**: landing page lets users choose "I'm an employee with a question" (consumer mode) or "I'm a legal professional" (attorney mode). Persistent mode indicator and disclaimer banner. | 3A.1 | Dual-mode layout |
| 3A.3 | Implement landing page with mode selection, value proposition, scope description, and starter questions (different per mode). | 3A.2 | Landing page |

#### 3B — Chat Interfaces (One per Mode)

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3B.1 | Implement **consumer chat**: message bubbles, plain-language rendering, source links with "as of" dates, suggested follow-up questions, "File a complaint" CTA when relevant. | 3A.2 | Consumer chat UI |
| 3B.2 | Implement **attorney chat**: message bubbles with Markdown rendering of legal analysis, statutory citation rendering (clickable links to leginfo sections), code cross-reference display, "Copy citation" functionality. | 3A.2 | Attorney chat UI |
| 3B.3 | Implement shared chat infrastructure: input component, conversation state, error handling, new conversation action. | 3B.1, 3B.2 | Chat infrastructure |
| 3B.4 | **[GATE]** Both modes functional end-to-end. Consumer gets plain-language answers with source URLs. Attorney gets legal analysis with clickable statutory citations. | 3A–3B | **Phase 3 complete** |

### Phase 4: Production Readiness (Unchanged)

Same as existing Phase 4 — infrastructure, deployment, monitoring, operations.

### Phase 5: Iteration & Expansion (Revised)

#### 5A — Source Expansion (Ongoing)

| # | Task | Priority | Deliverable |
|---|------|----------|-------------|
| 5A.1 | Ingest P2 agency sources: PERB, ALRB, CDE Child Labor, Cal/OSHA | P2 | Additional agency content |
| 5A.2 | Ingest P2 statutory codes: Health & Safety Code, Education Code, Civil Code | P2 | Additional statutory content |
| 5A.3 | Add California Code of Regulations (CCR) — administrative regulations implementing statutes | P3 | Regulatory content |
| 5A.4 | Automate content refresh: scheduled re-ingestion with change detection notifications | P2 | Automated freshness |
| 5A.5 | Non-English content support (Spanish first) | P3 | Multi-language knowledge base |

#### 5B — Experience Enhancements

| # | Task | Priority | Deliverable |
|---|------|----------|-------------|
| 5B.1 | Multi-turn conversation memory (separate context management per mode) | P2 | Conversation memory |
| 5B.2 | Attorney mode: "Related statutes" sidebar — when viewing a code section, show cross-referenced sections | P2 | Cross-reference UI |
| 5B.3 | Consumer mode: guided complaint filing workflow | P2 | Interactive workflow |
| 5B.4 | Feedback mechanism (thumbs up/down) with quality improvement loop | P2 | Feedback system |
| 5B.5 | Topic-guided browsing (by subject area: wages, discrimination, leave, safety, etc.) | P3 | Topic browse UI |

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

- [ ] **1.5A.1 — Design Source model and registry schema**
  - [ ] Define `sources` table in SQLite (id, name, slug, source_type, base_url, enabled, created_at)
  - [ ] Add `source_id` foreign key to `crawl_runs` table
  - [ ] Add `source_id` foreign key to `documents` table
  - [ ] Write schema migration script for existing CRD data
  - [ ] Create seed "CRD" source record in migration
  - [ ] Backfill existing crawl_runs and documents with CRD source_id
  - [ ] Add Source dataclass to `storage/models.py`
  - [ ] Add Source CRUD methods to `storage/storage.py` (create_source, get_source, get_all_sources, update_source)
  - [ ] Write unit tests for Source model and storage operations
  - [ ] Verify migration is idempotent (safe to run multiple times)

- [ ] **1.5A.2 — Source configuration loader**
  - [ ] Define per-source YAML schema (name, slug, type, base_url, enabled, seed_urls, allowlist_patterns, blocklist_patterns, content_selector, boilerplate_patterns, rate_limit_seconds, max_pages, chunking overrides)
  - [ ] Create `config/sources/` directory
  - [ ] Migrate existing `config/scraper.yaml` to `config/sources/crd.yaml` format
  - [ ] Implement `load_source_config(path)` function returning typed SourceConfig dataclass
  - [ ] Implement `load_all_source_configs(directory)` to load all enabled source configs
  - [ ] Add validation: required fields, regex compilation, rate limit bounds
  - [ ] Write unit tests for source config loading and validation
  - [ ] Write tests for malformed YAML, missing fields, invalid patterns

- [ ] **1.5A.3 — Refactor pipeline for source-aware execution**
  - [ ] Update `Pipeline.__init__` to accept a `SourceConfig` instead of (or in addition to) `CrawlConfig`
  - [ ] Update `pipeline.run()` to tag crawl_run with source_id
  - [ ] Update `pipeline.run()` to tag documents with source_id
  - [ ] Apply source-specific content_selector during HTML extraction
  - [ ] Refactor `clean()` in `cleaner.py` to accept an optional `boilerplate_patterns` parameter; fall back to existing CRD defaults when not provided (existing `_BOILERPLATE_PATTERNS` become the default, not the only option)
  - [ ] Apply source-specific boilerplate_patterns during cleaning by passing them from the source config through the pipeline to the cleaner
  - [ ] Update CLI `scrape` command: add `--source <slug>` flag (runs one source) and `--all` flag (runs all enabled)
  - [ ] Update CLI `status` command to show per-source statistics
  - [ ] Write integration tests for source-aware pipeline
  - [ ] Write CLI tests for `--source` and `--all` flags

- [ ] **1.5A.4 — Add content_category to data model**
  - [ ] Define `ContentCategory` enum: `agency_guidance`, `fact_sheet`, `statutory_code`, `regulation`, `poster`, `faq`
  - [ ] Add `content_category` column to `documents` table
  - [ ] Add `content_category` column to `chunks` table
  - [ ] Write migration to add columns with default `agency_guidance`
  - [ ] Implement URL/content-based heuristic to classify documents (e.g., PDF fact sheets → `fact_sheet`, FAQ pages → `faq`)
  - [ ] Backfill existing CRD data: classify as `agency_guidance` or `fact_sheet` based on URL patterns
  - [ ] Update pipeline to assign content_category during ingestion
  - [ ] Write unit tests for content categorization heuristics
  - [ ] Write migration tests

- [ ] **[GATE] 1.5A.5 — Backward compatibility validation**
  - [ ] Run `employee-help scrape --source crd` and verify identical behavior to Phase 1
  - [ ] All existing 162+ tests still pass
  - [ ] CRD data correctly tagged with source_id and content_category
  - [ ] New source can be added by creating a YAML config file (no code changes)
  - [ ] PO sign-off on multi-source foundation

---

#### 1.5B — Agency Source Expansion (DIR, EDD, CalHR)

> **Scheduling note:** 1.5B and 1.5C are independent of each other — both depend only on the 1.5A.5 gate. They **can and should run in parallel** to shorten the critical path. 1.5D depends on both completing.

**Goal:** Add three new agency sources to validate the multi-source architecture works in practice.

- [ ] **1.5B.1 — DIR/DLSE source configuration and spike**
  - [ ] [SPIKE] Crawl dir.ca.gov/dlse/ manually — identify content structure, navigation, content selectors
  - [ ] [SPIKE] Test Playwright vs. static HTML parsing for DIR pages
  - [ ] [SPIKE] Identify main content area selector for DIR
  - [ ] [SPIKE] Document DIR-specific boilerplate patterns (header, footer, nav, sidebar)
  - [ ] Create `config/sources/dir.yaml` with seed URLs, scope rules, selectors
  - [ ] Set allowlist patterns for employment/wage/hour content
  - [ ] Set blocklist patterns for non-relevant DIR content (e.g., mining, elevators)
  - [ ] Run spike crawl (first 20 pages) and review output quality
  - [ ] Document spike findings and any DIR-specific extraction challenges

- [ ] **1.5B.2 — EDD source configuration and spike**
  - [ ] [SPIKE] Crawl edd.ca.gov — identify content structure and selectors
  - [ ] [SPIKE] Determine if EDD uses ca.gov template (static HTML likely)
  - [ ] [SPIKE] Identify EDD content areas relevant to employee rights (UI, SDI, PFL)
  - [ ] Create `config/sources/edd.yaml` with seed URLs, scope rules, selectors
  - [ ] Set allowlist patterns for benefits/employee content
  - [ ] Set blocklist patterns (employer tax admin, internal tools, non-English)
  - [ ] Run spike crawl (first 20 pages) and review output quality
  - [ ] Document spike findings

- [ ] **1.5B.3 — CalHR source configuration and spike**
  - [ ] [SPIKE] Crawl calhr.ca.gov — identify content structure
  - [ ] [SPIKE] Investigate hrmanual.calhr.ca.gov subdomain (separate config?)
  - [x] [PO] Confirmed: Include CalHR in general knowledge base with "state_employees" metadata tag
  - [ ] Create `config/sources/calhr.yaml` with seed URLs, scope rules, selectors
  - [ ] Tag CalHR content with "state_employees" metadata flag (retrieval can de-prioritize for private-sector queries)
  - [ ] Run spike crawl (first 20 pages) and review output quality
  - [ ] Document spike findings

- [ ] **1.5B.4 — Full ingestion and quality check**
  - [ ] Run full pipeline for DIR source
  - [ ] Run full pipeline for EDD source
  - [ ] Run full pipeline for CalHR source
  - [ ] Spot-check 10 chunks per source for content quality
  - [ ] Verify content_category assignment accuracy
  - [ ] Verify no cross-source data contamination
  - [ ] Document per-source statistics (pages crawled, documents stored, chunks created, error rate)

- [ ] **[GATE] 1.5B.5 — Agency expansion validated**
  - [ ] Three new sources ingested with <5% error rate
  - [ ] Spot-check confirms content quality across all sources
  - [ ] Per-source run manifests generated
  - [ ] PO review of sample chunks from each source

---

#### 1.5C — Statutory Code Extractor

**Goal:** Build the statutory code ingestion pipeline for leginfo.legislature.ca.gov, starting with Labor Code and FEHA.

- [ ] **1.5C.1 — Leginfo technical spike**
  - [ ] [SPIKE] Navigate leginfo.legislature.ca.gov manually — document URL patterns
  - [ ] [SPIKE] Confirm URL pattern for TOC: `codesTOCSelected.xhtml?tocCode=LAB&tocTitle=...`
  - [ ] [SPIKE] Confirm URL pattern for sections: `codes_displaySection.xhtml?lawCode=LAB&sectionNum=...`
  - [ ] [SPIKE] Test Playwright rendering of leginfo JSF pages
  - [ ] [SPIKE] Test direct HTTP requests (may not need Playwright if server-rendered)
  - [ ] [SPIKE] Identify TOC HTML structure — how divisions/parts/chapters/articles are nested
  - [ ] [SPIKE] Identify section content HTML structure — where section text lives in the DOM
  - [ ] [SPIKE] Identify how leginfo displays effective dates and amendment history
  - [ ] [SPIKE] Test rate limiting and politeness (what's acceptable for a government site)
  - [ ] [SPIKE] Document findings: navigation strategy, URL construction, rendering approach, rate limits
  - [ ] [SPIKE] Estimate total section count for Labor Code and Gov Code FEHA sections

- [ ] **1.5C.2 — Statutory code extractor implementation**
  - [ ] Design `StatutoryExtractor` class interface (accepts code abbreviation + division list → yields sections)
  - [ ] Implement TOC traversal: given a code abbreviation, navigate the TOC to discover all divisions/parts/chapters/articles/sections
  - [ ] Implement section extraction: given a section URL, extract the section text
  - [ ] Implement citation metadata parsing:
    - [ ] Parse section number (including decimal subdivisions like "1102.5")
    - [ ] Parse subdivision markers (a), (b), (1), (2), (A), (B)
    - [ ] Extract division/part/chapter/article hierarchy path
    - [ ] Extract effective date / "as of" date
    - [ ] Generate canonical citation string (e.g., "Cal. Lab. Code § 1102.5")
  - [ ] Implement rate limiting specific to leginfo (configurable, default 3s)
  - [ ] Implement resumability: if pipeline crashes mid-code, can resume from last completed division
  - [ ] Implement repealed-section handling (F-SC.6): on re-ingestion, mark sections no longer present on leginfo as `is_active=False` rather than deleting them; add `is_active` boolean column to chunks table (default `True`)
  - [ ] Create `src/employee_help/scraper/extractors/statute.py`
  - [ ] Write unit tests with mock HTML fixtures (no live network calls in tests)
  - [ ] Write integration test that can optionally run against live leginfo (marked `@pytest.mark.live`)
  - [ ] Write tests for repealed-section soft-delete (re-ingest with a removed section → verify chunk marked inactive, not deleted)

- [ ] **1.5C.3 — Section-boundary chunking**
  - [ ] Add a `strategy` parameter to the chunker interface: `heading_based` (existing behavior for agency content) vs. `section_boundary` (new, for statutes). The source config's `chunking.strategy` field drives this — agency sources default to `heading_based`, statutory sources default to `section_boundary`. The existing `chunk_document()` function continues to work unchanged when no strategy is specified.
  - [ ] Implement `section_boundary` strategy: one code section = one chunk (default behavior)
  - [ ] Implement: if section exceeds max_tokens, split at subdivision boundaries
  - [ ] Ensure each resulting chunk carries the full citation metadata
  - [ ] Ensure section-boundary chunker preserves subdivision markers in content
  - [ ] Write unit tests for section-boundary chunking (normal sections, long sections, sections with many subdivisions)
  - [ ] Write tests verifying citation metadata is preserved on split chunks
  - [ ] Write regression tests confirming `heading_based` strategy (agency content) is unaffected by the new code

- [ ] **1.5C.4 — Code manifest configuration (P0 codes)**
  - [ ] Define code manifest YAML schema (code_name, code_abbreviation, target_divisions, citation_prefix)
  - [ ] Create `config/sources/labor_code.yaml`:
    - [ ] All 7 divisions of Labor Code [PO decision: comprehensive — all divisions]
    - [ ] Specify citation format: "Cal. Lab. Code"
  - [ ] Create `config/sources/gov_code_feha.yaml`:
    - [ ] Government Code §§ 12900–12996 (FEHA)
    - [ ] Government Code §§ 8547+ (whistleblower)
    - [ ] Specify citation format: "Cal. Gov. Code"
  - [ ] Validate configs load correctly with source config loader

- [ ] **1.5C.5 — P0 statutory ingestion run**
  - [ ] Run statutory pipeline for Labor Code
  - [ ] Run statutory pipeline for Government Code (FEHA + whistleblower)
  - [ ] Verify correct section count against leginfo TOC
  - [ ] Spot-check 20 randomly sampled sections: compare extracted text to leginfo web page
  - [ ] Verify citation metadata accuracy on spot-checked sections
  - [ ] Verify content_category = `statutory_code` on all statutory chunks
  - [ ] Document statistics: sections extracted, chunks created, token distribution, errors

- [ ] **[GATE] 1.5C.6 — Statutory pipeline validated**
  - [ ] Labor Code and FEHA fully ingested
  - [ ] Citation spot-check passes (20/20 sections match leginfo)
  - [ ] Section counts match expected totals
  - [ ] No missing divisions or articles
  - [ ] PO sign-off on statutory pipeline quality

- [ ] **1.5C.7 — Citation regression test suite**
  - [ ] Build a golden dataset of 50+ sections with known-correct citation strings (e.g., "Cal. Lab. Code § 1102.5(a)", "Cal. Gov. Code § 12940(j)(1)") — sourced from the 1.5C.5 spot-check plus additional hand-verified examples
  - [ ] Implement as an automated pytest suite: extract citation from stored chunk, compare to golden expected value
  - [ ] Run on every CI build to prevent citation parsing regressions from future code changes
  - [ ] Include edge cases: decimal section numbers (1102.5), deep subdivisions (a)(1)(A), repealed sections (marked inactive), sections with unusual numbering

---

#### 1.5D — P1 Sources & Cross-Source Validation

**Goal:** Ingest remaining P1 statutory codes and validate the full expanded knowledge base.

- [ ] **1.5D.1 — P1 statutory codes ingestion**
  - [ ] Create `config/sources/unemp_ins_code.yaml` (Unemployment Insurance Code — Div. 1)
  - [ ] Create `config/sources/bus_prof_code.yaml` (Business & Professions Code — §§ 16600–16607, 17200–17210)
  - [ ] Create `config/sources/ccp.yaml` (Code of Civil Procedure — § 340, § 425.16, § 1021.5)
  - [ ] Create `config/sources/gov_code_whistleblower.yaml` (Government Code whistleblower sections, if not covered in 1.5C.4)
  - [ ] Run statutory pipeline for each P1 code
  - [ ] Spot-check 10 sections per code for accuracy
  - [ ] Verify citation metadata accuracy

- [ ] **1.5D.2 — Cross-source duplicate detection**
  - [ ] Implement cross-source content_hash match detection: identify cases where the same content appears from different sources (e.g., a statute quoted verbatim in an agency guidance page)
  - [ ] Define resolution strategy: keep both chunks with their respective content_categories (a statute chunk and a guidance chunk may quote the same text but serve different retrieval purposes); flag exact duplicates in the validation report for PO review
  - [ ] Write tests for duplicate detection across sources

- [ ] **1.5D.3 — Comprehensive cross-source validation**
  - [ ] Generate full knowledge base statistics:
    - [ ] Total sources ingested (count by type: agency vs. statutory)
    - [ ] Total documents stored (count by source)
    - [ ] Total chunks created (count by source and content_category)
    - [ ] Token count distribution (min, max, avg, median — overall and per source)
    - [ ] Content category distribution pie chart data
  - [ ] Run idempotency re-run on 2 sources (1 agency, 1 statutory) — verify 0 new documents
  - [ ] Citation sample validation: randomly select 30 statutory chunks, verify citation strings
  - [ ] Content quality validation: randomly select 20 agency chunks, verify formatting and relevance
  - [ ] Cross-reference check: verify no duplicate content across sources (use 1.5D.2 detection output)
  - [ ] Generate validation report (JSON + Markdown)

- [ ] **1.5D.4 — Automated content refresh (PO Decision #5)**
  - [ ] Implement `employee-help refresh --source <slug>` and `--all` CLI commands (re-runs pipeline, uses content_hash to skip unchanged content)
  - [ ] Add change detection reporting: after a refresh run, log which documents had new content vs. unchanged
  - [ ] Create cron configuration (or equivalent scheduler) with recommended cadence: weekly for agency sources, monthly for statutory codes
  - [ ] Write tests for change detection logic (unchanged content → 0 new docs; changed content → updated docs)

- [ ] **1.5D.5 — Performance baseline (NF-2)**
  - [ ] Time full pipeline run for each agency source; verify each completes within 30 minutes
  - [ ] Time full statutory pipeline for Labor Code; verify completes within 2 hours
  - [ ] Document per-source timing baselines (pages/min, sections/min, total duration)
  - [ ] If any source exceeds threshold, investigate and document bottleneck (network, extraction, or storage)

- [ ] **[GATE] 1.5D.6 — Phase 1.5 acceptance**
  - [ ] All P0 and P1 sources ingested
  - [ ] Validation report shows acceptable quality metrics
  - [ ] Idempotency confirmed
  - [ ] Citation accuracy verified
  - [ ] PO approves expanded knowledge base as foundation for Phase 2
  - [ ] **Phase 1.5 COMPLETE**

---

### Phase 2: RAG Pipeline & Answer Generation

#### 2A — Embedding & Semantic Search

**Goal:** Generate vector embeddings for all chunks and build dual-mode retrieval.

- [ ] **2A.1 — Embedding and vector search evaluation**
  - [ ] [SPIKE] Evaluate embedding model options:
    - [ ] OpenAI text-embedding-3-small/large (API cost at 50K–100K chunks)
    - [ ] Open-source alternatives (sentence-transformers, Instructor) for local generation
  - [ ] [SPIKE] Evaluate vector database options:
    - [ ] ChromaDB (embedded, simple, good for MVP)
    - [ ] Qdrant (more features, still embeddable)
    - [ ] pgvector (if considering PostgreSQL migration)
  - [ ] [SPIKE] Benchmark at scale: generate test embeddings for 1,000 chunks, measure storage size, query latency
  - [ ] [SPIKE] Verify metadata filtering support (filter by content_category, source_id)
  - [ ] [SPIKE] Test hybrid search capability (semantic + keyword) for citation lookup
  - [ ] Write Architecture Decision Record (ADR) with findings and recommendation

- [ ] **[GATE] 2A.1b — Embedding/vector approach decision**
  - [ ] [PO] Review ADR and approve embedding model + vector database selection
  - [ ] If no suitable vector solution meets requirements at scale, fallback plan: implement enhanced keyword search with BM25 ranking + metadata filtering as interim retrieval layer; revisit vector search when scale demands it
  - [ ] Approved approach documented; 2A.2 proceeds with selected technology

- [ ] **2A.2 — Embedding generation pipeline**
  - [ ] Implement embedding generation service (wraps chosen model API)
  - [ ] Implement batch embedding with rate limiting and error handling
  - [ ] Implement incremental embedding (only embed new/changed chunks)
  - [ ] Store embeddings with metadata: chunk_id, source_id, content_category, citation (if statutory)
  - [ ] Add CLI command: `employee-help embed --source <slug>` and `--all`
  - [ ] Add CLI command: `employee-help embed-status` (show embedding coverage)
  - [ ] Write unit tests for embedding service
  - [ ] Write integration tests for batch embedding

- [ ] **2A.3 — Dual-mode retrieval service**
  - [ ] Implement `RetrievalService` with `retrieve(query, mode, top_k)` method
  - [ ] Implement **consumer mode** retrieval:
    - [ ] Filter to content_categories: `agency_guidance`, `fact_sheet`, `faq`
    - [ ] Pure semantic similarity ranking
    - [ ] Return source URLs with documents
  - [ ] Implement **attorney mode** retrieval:
    - [ ] Include all content_categories, boost `statutory_code` relevance
    - [ ] Hybrid search: semantic for concept matching + keyword for citation lookup (e.g., "§ 1102.5")
    - [ ] Return citation metadata with statutory chunks
    - [ ] Return cross-references when available
  - [ ] Implement **shared** retrieval infrastructure:
    - [ ] Query preprocessing (expand abbreviations, normalize legal terms)
    - [ ] Result deduplication (same content from overlapping chunks)
    - [ ] Source diversity (don't return 5 chunks from the same document)
  - [ ] Write unit tests for both modes
  - [ ] Write integration tests with real embedded chunks

- [ ] **[GATE] 2A.4 — Search quality benchmark**
  - [ ] Create evaluation dataset: 20+ consumer questions with expected relevant content
  - [ ] Create evaluation dataset: 20+ attorney questions with expected statutory sections
  - [ ] Run consumer questions through consumer mode, measure recall@5 and precision@5
  - [ ] Run attorney questions through attorney mode, measure recall@5 and precision@5
  - [ ] Attorney mode must return correct statutory section in top-5 for citation-specific queries
  - [ ] Document benchmark results
  - [ ] PO sign-off on search quality

---

#### 2B — LLM Integration & Dual-Mode Answer Generation

**Goal:** Connect retrieval to an LLM for generating mode-appropriate answers.

- [ ] **2B.1 — Prompt template design**
  - [ ] Design **consumer mode** prompt template:
    - [ ] System prompt: role, tone (supportive, clear, non-legal-advice), scope
    - [ ] Context injection format: how retrieved chunks are presented to the LLM
    - [ ] Citation format: "According to [Agency Name]..." with source URL
    - [ ] Disclaimer: "This information is for educational purposes and is not legal advice"
    - [ ] Actionable next steps: when to suggest filing a complaint, contacting an agency, consulting an attorney
  - [ ] Design **attorney mode** prompt template:
    - [ ] System prompt: role, tone (professional legal analysis), scope
    - [ ] Context injection format: statutory sections with full citations
    - [ ] Citation format: "Cal. Lab. Code § 1102.5 provides that..." with leginfo link
    - [ ] Analysis structure: elements, burden of proof, defenses, remedies
    - [ ] Cross-reference format: "See also Cal. Gov. Code § 12940(a)"
    - [ ] Disclaimer: "This analysis is AI-generated and should be independently verified"
  - [ ] Review prompts with domain knowledge (employment law basics)
  - [ ] Write tests that prompt templates render correctly with sample data

- [ ] **2B.2 — RAG answer generation service**
  - [ ] Implement `AnswerService` with `generate(query, mode) → Answer` method
  - [ ] Implement answer pipeline: query → retrieve(mode) → build prompt → call LLM → format response
  - [ ] Implement LLM client wrapper (support OpenAI API and Claude API)
  - [ ] Implement response formatting:
    - [ ] Consumer: plain text with embedded source links
    - [ ] Attorney: Markdown with citation formatting, section references, analysis structure
  - [ ] Implement streaming support (for real-time UI display in Phase 3)
  - [ ] Implement token budget management (stay within context limits)
  - [ ] Implement error handling: LLM timeout, rate limits, content policy
  - [ ] Add CLI command: `employee-help ask "question" --mode consumer|attorney`
  - [ ] Write unit tests for answer service
  - [ ] Write integration tests with real LLM calls (marked `@pytest.mark.llm`)

- [ ] **2B.3 — Quality evaluation**
  - [ ] Create evaluation dataset: 20+ consumer Q&A pairs with expected answer elements
  - [ ] Create evaluation dataset: 20+ attorney Q&A pairs with expected citations and analysis elements
  - [ ] Run evaluation:
    - [ ] Grade each answer for factual accuracy (does it match source material?)
    - [ ] Grade each answer for citation correctness (attorney mode: are citations real and relevant?)
    - [ ] Grade each answer for appropriate tone (consumer: accessible; attorney: professional)
    - [ ] Grade each answer for disclaimer presence
    - [ ] Grade each answer for actionable next steps (consumer mode)
  - [ ] Document evaluation results with scores and examples
  - [ ] Identify failure patterns and adjust prompts/retrieval as needed

- [ ] **[GATE] 2B.4 — Dual-mode RAG validated**
  - [ ] Consumer mode produces accurate, plain-language, well-sourced answers
  - [ ] Attorney mode produces accurate legal analysis with correct statutory citations
  - [ ] Citations verified against leginfo (attorney mode)
  - [ ] Appropriate disclaimers present in both modes
  - [ ] PO sign-off on answer quality
  - [ ] **Phase 2 COMPLETE**

---

### Phase 3: Web Application (Dual-Mode)

#### 3A — Application Shell

**Goal:** Build the Reflex web app skeleton with mode selection and shared infrastructure.

- [ ] **3A.1 — Reflex project initialization**
  - [ ] Initialize Reflex project in appropriate directory
  - [ ] Create app state class wrapping dual-mode RAG service
  - [ ] Configure Reflex with environment-based settings (dev/prod)
  - [ ] Set up project structure (pages, components, state, styles)
  - [ ] Verify basic Reflex app runs locally

- [ ] **3A.2 — Mode selection and layout**
  - [ ] Design and implement landing page layout
  - [ ] Implement mode selector: "I'm an employee with a question" vs. "I'm a legal professional"
  - [ ] Implement persistent mode indicator (header/sidebar badge)
  - [ ] Implement mode-specific disclaimer banners
  - [ ] Implement shared navigation (mode switch, new conversation, about)
  - [ ] Implement responsive layout (desktop + mobile)
  - [ ] Write component tests

- [ ] **3A.3 — Landing page implementation**
  - [ ] Value proposition copy (different per mode)
  - [ ] Scope description: what topics are covered
  - [ ] Starter questions (5+ per mode, clickable to start a conversation)
  - [ ] Legal disclaimer (always visible)
  - [ ] Links to source agencies
  - [ ] Write page tests

---

#### 3B — Chat Interfaces

**Goal:** Build mode-specific chat experiences sharing one knowledge base.

- [ ] **3B.1 — Consumer chat interface**
  - [ ] Implement chat message bubbles (user + assistant)
  - [ ] Implement plain-language answer rendering
  - [ ] Implement source link display ("as of" dates, clickable URLs)
  - [ ] Implement suggested follow-up questions (generated from context)
  - [ ] Implement "File a complaint" CTA button when relevant
  - [ ] Implement "I need more help" → link to relevant agency
  - [ ] Implement input component with placeholder text
  - [ ] Implement loading state (streaming response display)
  - [ ] Write component tests

- [ ] **3B.2 — Attorney chat interface**
  - [ ] Implement chat message bubbles (user + assistant)
  - [ ] Implement Markdown rendering for legal analysis
  - [ ] Implement statutory citation rendering:
    - [ ] Clickable links to leginfo sections
    - [ ] Formatted with standard legal citation style
  - [ ] Implement code cross-reference display (sidebar or inline)
  - [ ] Implement "Copy citation" button for individual citations
  - [ ] Implement "Copy full analysis" button
  - [ ] Implement input component with placeholder text
  - [ ] Implement loading state (streaming response display)
  - [ ] Write component tests

- [ ] **3B.3 — Shared chat infrastructure**
  - [ ] Implement conversation state management
  - [ ] Implement message history (current session)
  - [ ] Implement "New conversation" action (clears history)
  - [ ] Implement error handling UI (LLM errors, network errors, rate limits)
  - [ ] Implement input validation and sanitization
  - [ ] Implement keyboard shortcuts (Enter to send, Shift+Enter for newline)
  - [ ] Write integration tests (end-to-end: input → API → response → display)

- [ ] **[GATE] 3B.4 — Phase 3 acceptance**
  - [ ] Consumer mode: end-to-end functional (question → plain-language answer with sources)
  - [ ] Attorney mode: end-to-end functional (question → legal analysis with clickable citations)
  - [ ] Mode switching works seamlessly
  - [ ] Mobile responsive
  - [ ] Disclaimers visible in both modes
  - [ ] PO sign-off on user experience
  - [ ] **Phase 3 COMPLETE**

---

### Phase 4: Production Readiness

**Goal:** Deploy the application to production with monitoring and operational controls.

- [ ] **4.1 — Infrastructure setup**
  - [ ] [PO] Select hosting provider (cloud provider, VPS, or PaaS)
  - [ ] Set up production environment (server, domain, SSL)
  - [ ] Configure production database (SQLite → PostgreSQL if needed at scale)
  - [ ] Set up vector database in production
  - [ ] Configure LLM API keys and environment variables
  - [ ] Set up environment-specific configuration (dev, staging, production)

- [ ] **4.2 — Deployment pipeline**
  - [ ] Set up CI/CD pipeline (GitHub Actions or similar)
  - [ ] Automated test suite runs on every PR
  - [ ] Automated linting and type checking
  - [ ] Staging deployment on merge to main
  - [ ] Production deployment with manual approval gate
  - [ ] Database migration automation
  - [ ] Rollback procedure documented and tested

- [ ] **4.3 — Monitoring and observability**
  - [ ] Application error tracking (Sentry or similar)
  - [ ] Structured log aggregation
  - [ ] API response time monitoring
  - [ ] LLM API usage and cost tracking
  - [ ] Vector database query performance monitoring
  - [ ] Uptime monitoring and alerting
  - [ ] Usage analytics (queries per day, mode split, popular topics)

- [ ] **4.4 — Security and compliance**
  - [ ] No PII collection or storage (verify)
  - [ ] Rate limiting on public API endpoints
  - [ ] Input sanitization (prevent prompt injection)
  - [ ] HTTPS enforced
  - [ ] Dependency vulnerability scanning
  - [ ] Legal disclaimer review (actual attorney review recommended)

- [ ] **4.5 — Operational procedures**
  - [ ] Content refresh runbook (how to re-ingest sources)
  - [ ] Incident response procedure
  - [ ] Backup and recovery procedure
  - [ ] Cost monitoring and budget alerts (LLM API costs)
  - [ ] On-call rotation (if applicable)

- [ ] **[GATE] 4.6 — Production launch**
  - [ ] All monitoring in place
  - [ ] Security review complete
  - [ ] Runbooks documented
  - [ ] Staging environment validated
  - [ ] PO sign-off on production readiness
  - [ ] **Phase 4 COMPLETE — PRODUCTION LAUNCH**

---

### Phase 5: Iteration & Expansion

#### 5A — Source Expansion (Ongoing)

- [ ] **5A.1 — P2 agency sources**
  - [ ] Create and validate `config/sources/perb.yaml` (Public Employment Relations Board)
  - [ ] Create and validate `config/sources/alrb.yaml` (Agricultural Labor Relations Board)
  - [ ] Create and validate `config/sources/cde.yaml` (CDE Child Labor)
  - [ ] Create and validate `config/sources/cal_osha.yaml` (Cal/OSHA — via DIR)
  - [ ] Run full pipeline for each; spot-check quality

- [ ] **5A.2 — P2 statutory codes**
  - [ ] Create and validate `config/sources/health_safety_code.yaml`
  - [ ] Create and validate `config/sources/education_code.yaml` (child labor sections)
  - [ ] Create and validate `config/sources/civil_code.yaml` (relevant employment sections)
  - [ ] Run statutory pipeline for each; verify citation accuracy

- [ ] **5A.3 — California Code of Regulations (CCR)**
  - [ ] [SPIKE] Investigate CCR source (regulations.ca.gov or westlaw/lexis alternative)
  - [ ] Implement CCR extractor if new source structure
  - [ ] Ingest employment-related CCR titles (Title 2, Title 8)
  - [ ] Tag as `regulation` content_category

- [ ] **5A.4 — Automated content refresh**
  - [ ] Implement scheduled re-ingestion (cron job or task scheduler)
  - [ ] Implement change detection: compare new content hashes to stored hashes
  - [ ] Implement notification on content changes (email or Slack webhook)
  - [ ] Implement re-embedding for changed chunks only
  - [ ] Write tests for change detection logic

- [ ] **5A.5 — Non-English content support**
  - [ ] [PO] Decide: Spanish first? Which agencies have Spanish content?
  - [ ] Add `language` metadata to source configs and chunks
  - [ ] Implement language-aware retrieval (match user's language preference)
  - [ ] Evaluate multilingual embedding model
  - [ ] Ingest Spanish-language fact sheets from CRD and DIR

---

#### 5B — Experience Enhancements

- [ ] **5B.1 — Multi-turn conversation memory**
  - [ ] Implement conversation session storage (per-user, per-session)
  - [ ] Implement context window management (summarize older turns)
  - [ ] Mode-specific context handling (consumer: simpler; attorney: preserve citations)
  - [ ] Write tests for conversation memory

- [ ] **5B.2 — Attorney mode: related statutes sidebar**
  - [ ] Implement cross-reference extraction from statutory text (detect "Section XXXX" references)
  - [ ] Build cross-reference index during ingestion
  - [ ] Display "Related statutes" sidebar when viewing statutory citations
  - [ ] Clickable cross-references that link to the referenced section

- [ ] **5B.3 — Consumer mode: guided complaint filing**
  - [ ] Design complaint filing wizard (agency selection, issue type, next steps)
  - [ ] Implement step-by-step workflow UI
  - [ ] Link to appropriate agency complaint form at each step
  - [ ] Include timeline expectations and documentation checklists

- [ ] **5B.4 — Feedback mechanism**
  - [ ] Implement thumbs up/down on each answer
  - [ ] Store feedback with question, answer, mode, and rating
  - [ ] Build feedback review dashboard
  - [ ] Use feedback to identify quality improvement opportunities
  - [ ] Periodic prompt tuning based on negative feedback patterns

- [ ] **5B.5 — Topic-guided browsing**
  - [ ] Implement topic taxonomy navigation (Wages, Discrimination, Leave, Safety, etc.)
  - [ ] Pre-built queries per topic for quick access
  - [ ] Topic landing pages with key information and common questions
  - [ ] Browse by agency or by topic dimension

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

---

## 8. Phase Summary (Revised)

| Phase | Focus | Key Outcome |
|-------|-------|-------------|
| **Phase 1** ✅ | CRD Knowledge Acquisition | CRD employment discrimination content in SQLite (done) |
| **Phase 1.5** (NEW) | Multi-Source & Statutory Expansion | 8+ agency sources + statutory codes with citation metadata |
| **Phase 2** (Revised) | Dual-Mode RAG Pipeline | Consumer + attorney answer generation with mode-appropriate retrieval and citation |
| **Phase 3** (Revised) | Dual-Mode Web Application | Two chat experiences sharing one knowledge base |
| **Phase 4** | Production Deployment | Live, monitored, cost-tracked platform |
| **Phase 5** | Iteration & Expansion | P2 sources, CCR regulations, conversation memory, cross-references |

> **Phases 1–4 are the MVP path.** Phase 1.5 adds ~15–20 tasks. The dual-mode experience in Phases 2–3 adds complexity but delivers dramatically more value than a single-mode approach.

---

## 9. Product Owner Decisions (Resolved)

| # | Question | Decision | Impact |
|---|----------|----------|--------|
| 1 | **Phase 1.5 vs. Phase 2 priority** | **A) Sources first (1.5 → 2 → 3).** Build the broad data foundation before the chatbot. | The first user-facing chatbot will cover all employment rights topics from day one. No rework on embeddings/prompts when sources expand. |
| 2 | **Statutory code depth** | **A) All 7 Labor Code divisions (comprehensive).** Full ingestion (~4,000 sections). | Attorneys get the complete statutory foundation from the start. Longer Phase 1.5C but maximizes the investment in citation infrastructure. |
| 3 | **Attorney mode MVP scope** | **A) Full citation mode from day one.** Attorney mode launches with precise § references, clickable leginfo links, and legal analysis structure. | Phase 2–3 are more complex, but the core attorney value proposition is delivered immediately. Consistent with the comprehensive statutory ingestion decision. |
| 4 | **CalHR scope** | **A) Include with metadata tag.** CalHR content ingested into the unified knowledge base, tagged with "state_employees" metadata flag for filtering. | One knowledge base, metadata-driven filtering. Retrieval can de-prioritize CalHR content for private-sector questions. |
| 5 | **Content refresh cadence** | **A) Add basic automation (cron) in Phase 1.5.** Weekly for agencies, monthly for statutory codes, with change detection. | Keeps content fresh without manual effort. Adds ~2–3 tasks to Phase 1.5D. |

---

## 10. Product Owner Decisions (Previously Resolved — Still Valid)

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
