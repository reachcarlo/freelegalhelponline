# Phase 1: Knowledge Repository Acquisition — Employment Discrimination (California Civil Rights Department)

> **Project:** Employee Help — AI-Powered Legal Guidance Assistant
> **Author:** Claude (Opus 4.6) for Product Owner review
> **Date:** 2026-02-24
> **Status:** DRAFT — Awaiting PO approval

---

## Preamble: Pressure-Test Analysis

Before finalizing requirements, the following assumptions were stress-tested through Product Management, Technical Architecture, Software Architecture, and Business Analysis lenses.

### Initial Assumptions Examined

| # | Assumption | Lens | Challenge | Resolution |
|---|-----------|------|-----------|------------|
| 1 | "We only need to scrape HTML pages" | Technical Architect | The CRD site (calcivilrights.ca.gov) is WordPress/Divi-based. Critical content lives in **PDFs** (fact sheets, brochures, posters, policy samples) — not just HTML pages. A pure HTML scraper misses ~40-50% of the actionable legal content. | The acquisition pipeline must handle **both HTML page content and PDF documents**. PDF extraction is a first-class concern, not an afterthought. |
| 2 | "A simple web scraper will work" | Technical Architect | The Divi theme renders significant content client-side (JavaScript-driven accordions, tabbed layouts, lazy-loaded sections). Standard HTTP GET + HTML parsing (e.g., `requests` + `BeautifulSoup`) will miss dynamically rendered content. | Use a headless browser (Playwright) for page rendering, then extract content from the fully rendered DOM. Fall back to static parsing only where appropriate. |
| 3 | "We scrape once and we're done" | Product Manager | Legal content changes — new laws take effect annually (e.g., SB 464 for 2026), fact sheets get updated, CRD publishes new guidance. A one-shot scrape creates a stale knowledge base that could deliver **outdated or incorrect legal information**. | Design the pipeline as **re-runnable and diff-aware** from day one. Track content versions. Architect for periodic refresh, even if we don't automate it in Phase 1. |
| 4 | "All CRD employment pages are relevant" | Business Analyst | The CRD site covers housing, hate violence, whistleblower, and other domains beyond employment discrimination. Scraping too broadly pollutes the knowledge base; scraping too narrowly misses relevant cross-cutting content (e.g., the complaint process applies to all CRD domains but is essential context for employment advice). | Define an explicit **content scope boundary** with inclusion/exclusion rules. Employment discrimination is the core; complaint process and FEHA overview are in-scope as supporting context. Housing, hate violence, etc., are out of scope for Phase 1. |
| 5 | "Raw scraped text is enough for AI retrieval" | Software Architect | Large language models perform poorly on long, unstructured text dumps. Retrieval-Augmented Generation (RAG) requires content to be **chunked, enriched with metadata, and embedded** for semantic search. Raw scrape output is an intermediate artifact, not the final knowledge format. | The pipeline must produce **structured, chunked documents with metadata** (source URL, section hierarchy, content type, last-modified date) — not just raw text files. |
| 6 | "We can store everything in flat files" | Technical Architect | Flat files work for initial prototyping but fail at: semantic search, metadata filtering, version tracking, and scale. However, over-engineering storage in Phase 1 (e.g., deploying a vector database cluster) adds complexity before we've validated the content pipeline. | Use **SQLite** for structured metadata + content storage in Phase 1. Write it as a straightforward module with clean function signatures — no abstract base classes or repository patterns. If we migrate to PostgreSQL later, we refactor; the abstraction wouldn't save meaningful time since SQL dialects and libraries differ anyway. |
| 7 | "Legal disclaimers aren't our concern yet" | Product Manager / BA | This application provides legal information based on government sources. Even in Phase 1 (no user-facing chat yet), the **provenance and accuracy** of stored content is a liability concern. If we lose track of where content came from, the entire knowledge base is compromised. | Every stored document chunk must carry **full provenance metadata**: source URL, retrieval timestamp, content hash, and source document title. This is non-negotiable infrastructure, not a nice-to-have. |
| 8 | "The Python web framework choice can wait" | Software Architect | Phase 1 is a data pipeline, not a web app — but framework choice now affects how the pipeline integrates later. Choosing an incompatible stack creates migration pain. However, the scraper itself should be framework-agnostic. | Select the web framework now for architectural alignment. Use **Reflex** as a single full-stack framework (Python frontend + backend in one process). Avoid splitting into two servers (e.g., FastAPI + separate frontend) — Reflex handles both, and the RAG service integrates as a Python module that Reflex state handlers call directly. Keep the scraping pipeline as a **standalone module** with clean interfaces that the web layer imports. |

### Key Risks Identified

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Delivering outdated legal information** | Critical | Provenance tracking, content versioning, clear "as of" dates on all stored content |
| **Missing content from JS-rendered pages** | High | Headless browser rendering; manual audit of scraped vs. actual page content |
| **PDF extraction quality** | High | Use robust PDF extraction (pdfplumber/PyMuPDF); include quality validation step |
| **Scope creep into non-employment content** | Medium | Explicit URL allowlist and content-type filters in scraper configuration |
| **Legal liability from AI-generated advice** | Critical | Out of scope for Phase 1 implementation, but the knowledge base design must support disclaimer injection and source attribution from day one |

---

## 1. Vision & Context

### 1.1 Product Vision

Build an AI-powered web application that helps California employees and job applicants understand their rights under state employment discrimination law. The application will provide accurate, source-attributed guidance by querying a curated knowledge base derived from official California Civil Rights Department (CRD) publications.

### 1.2 Phase 1 Objective

**Acquire, process, and store** the employment discrimination knowledge corpus from the California Civil Rights Department website (`calcivilrights.ca.gov`) in a structured, query-ready format that can serve as the retrieval layer for a future AI chat assistant.

### 1.3 What Phase 1 Is NOT

- Not building the web frontend or chat interface (Phase 2)
- Not integrating with an LLM for answer generation (Phase 2)
- Not deploying to production (Phase 3)
- Not covering non-employment CRD content (future phases)

---

## 2. Content Scope

### 2.1 In-Scope Sources

| Source Type | Examples | Priority |
|-------------|----------|----------|
| **Primary HTML pages** | `/employment/` main page and all linked employment sub-pages | P0 |
| **PDF fact sheets** | Pregnancy Disability Leave, Family Care & Medical Leave, Age Discrimination, Fair Chance Act (Criminal History), Retaliation, Transgender/Gender Nonconforming Rights | P0 |
| **PDF brochures & posters** | "Discrimination is Against the Law" brochure, Workplace Discrimination & Harassment poster, Sexual Harassment poster | P0 |
| **Policy & guidance documents** | CRD Sample EEO Policy, Harassment Prevention Guide, Sexual Harassment Prevention Training FAQ | P1 |
| **Complaint process** | `/complaintprocess/` page — filing procedures, timelines, what to expect | P0 |
| **Regulatory text** | FEHA regulations, employment-related regulatory amendments | P2 |

### 2.2 Out-of-Scope for Phase 1

- Housing discrimination content
- Hate violence content
- Whistleblower / Ralph Civil Rights Act content
- CRD annual reports (statistical, not guidance-oriented)
- Non-English language versions (future phase)
- Third-party legal commentary or case law

### 2.3 Known Content Inventory (Discovered via Research)

**HTML Pages:**
- `calcivilrights.ca.gov/employment/` — Main employment discrimination page
- `calcivilrights.ca.gov/complaintprocess/` — Complaint filing process
- Sub-pages linked from the employment page (to be fully enumerated by the scraper)

**PDF Documents (confirmed URLs):**
- Employment Discrimination Based on Disability fact sheet
- Pregnancy Disability Leave fact sheet
- Family Care and Medical Leave fact sheet
- Age Discrimination in Employment fact sheet
- Fair Chance Act (Criminal History & Employment) fact sheet
- Retaliation fact sheet
- Transgender/Gender Nonconforming Employee Rights fact sheet
- Workplace Discrimination & Harassment poster
- Sexual Harassment poster
- Sexual Harassment Prevention Training FAQ (employers)
- CRD Sample EEO Policy
- Harassment Prevention Guide (2025 edition)
- "Discrimination is Against the Law" brochure

---

## 3. Functional Requirements

### 3.1 Content Discovery

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-1.1 | The scraper shall crawl the CRD employment page and **automatically discover** all linked sub-pages within the defined scope boundary. | Manual URL curation doesn't scale and misses new pages. |
| F-1.2 | The scraper shall discover and catalog all **PDF documents** linked from in-scope pages. | Critical content lives in PDFs (see Pressure Test #1). |
| F-1.3 | The scraper shall respect a **configurable URL allowlist/blocklist** to enforce content scope boundaries. | Prevents scope creep into housing, hate violence, etc. (Pressure Test #4). |
| F-1.4 | The scraper shall log all discovered URLs and their crawl status (visited, skipped, failed, out-of-scope). | Auditability and debugging. |

### 3.2 Content Extraction

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-2.1 | HTML pages shall be rendered via **headless browser** before content extraction to capture JS-rendered content. | Divi theme renders content client-side (Pressure Test #2). |
| F-2.2 | PDF documents shall be extracted using a dedicated PDF parsing library that preserves **text structure** (headings, lists, paragraphs). | PDF content is as important as HTML (Pressure Test #1). |
| F-2.3 | Extracted content shall preserve **semantic structure**: headings hierarchy, lists, emphasis, and section boundaries. | Structure is essential for accurate chunking and retrieval. |
| F-2.4 | Navigation chrome, footers, sidebars, and cookie banners shall be **stripped** from extracted content. | Noise reduces retrieval accuracy. |

### 3.3 Content Processing & Storage

| ID | Requirement | Rationale |
|----|-------------|-----------|
| F-3.1 | Extracted content shall be **chunked** into retrieval-ready segments (target: 500-1500 tokens per chunk with contextual overlap). | RAG systems require appropriately sized chunks (Pressure Test #5). |
| F-3.2 | Each chunk shall carry **provenance metadata**: source URL, document title, section heading path, content type (HTML/PDF), retrieval timestamp, and content hash. | Non-negotiable for legal accuracy and attribution (Pressure Test #7). |
| F-3.3 | Content shall be stored in a **SQLite database** with a schema designed for future migration to PostgreSQL + vector store. | Right-sized for Phase 1; migration-ready (Pressure Test #6). |
| F-3.4 | The pipeline shall be **idempotent**: re-running the scraper updates existing records (based on content hash comparison) rather than creating duplicates. | Supports content refresh without data corruption (Pressure Test #3). |
| F-3.5 | The pipeline shall produce a **run manifest** summarizing: pages crawled, documents processed, chunks created, errors encountered, and content changes detected. | Operational visibility for the PO and future monitoring. |

---

## 4. Non-Functional Requirements

| ID | Requirement | Rationale |
|----|-------------|-----------|
| NF-1 | The scraper shall implement **polite crawling**: configurable rate limiting (default: 2-second delay between requests), respect for `robots.txt`. | Responsible use of a government website. |
| NF-2 | The pipeline shall complete a **full scrape** within 15 minutes on a standard development machine. | Developer experience; CI/CD feasibility. |
| NF-3 | All configuration (URLs, rate limits, scope rules, chunk sizes) shall be externalized in a **configuration file**, not hardcoded. | Operability and adaptability without code changes. |
| NF-4 | The pipeline shall provide **structured logging** (JSON format) at configurable verbosity levels. | Debugging, audit trail, operational monitoring. |
| NF-5 | The codebase shall include a **test suite** covering: URL filtering logic, content cleaning, chunking, metadata extraction, and storage operations. | Quality assurance; prevents regressions when scope expands. |

---

## 5. Architectural Decisions

### 5.1 Technology Stack (Phase 1)

| Concern | Choice | Rationale |
|---------|--------|-----------|
| **Language** | Python 3.12+ | User requirement; ecosystem strength for NLP/AI |
| **Web framework** (selected now, used Phase 2+) | Reflex | Pure-Python full-stack framework; handles both frontend (React-based UI) and backend (state management, API routes) in a single process. No JavaScript required. Eliminates the complexity of running two separate servers. The RAG service integrates as a Python module called by Reflex state handlers. |
| **HTML scraping** | Playwright (headless Chromium) | Handles JS-rendered Divi content; async-native; robust |
| **HTML parsing** | BeautifulSoup4 | Post-render DOM parsing; mature, well-documented |
| **PDF extraction** | pdfplumber | Preserves layout structure; handles tables; pure Python |
| **Storage** | SQLite (via Python `sqlite3`) | Zero-dependency; sufficient for Phase 1 volumes; schema designed for future migration |
| **Configuration** | YAML config file | Human-readable; supports nested structures for scope rules |
| **Logging** | Python `structlog` | Structured JSON logging; composable processors |
| **Testing** | pytest | Standard; rich plugin ecosystem |
| **Dependency management** | `uv` + `pyproject.toml` | Modern, fast Python package management |

### 5.2 Module Structure (Phase 1)

```
employee_help/
├── pyproject.toml
├── config/
│   └── scraper.yaml              # Scope rules, rate limits, target URLs
├── src/
│   └── employee_help/
│       ├── scraper/
│       │   ├── crawler.py        # URL discovery and page fetching
│       │   ├── extractors/
│       │   │   ├── html.py       # HTML content extraction
│       │   │   └── pdf.py        # PDF content extraction
│       │   ├── pipeline.py       # Orchestrates crawl → extract → process → store
│       │   └── config.py         # Configuration loader
│       ├── processing/
│       │   ├── cleaner.py        # Content cleaning (strip nav, boilerplate)
│       │   └── chunker.py        # Text chunking with overlap
│       ├── storage/
│       │   ├── models.py         # Data models (Document, Chunk, CrawlRun)
│       │   └── storage.py        # SQLite implementation (direct, no abstraction layer)
│       └── cli.py                # CLI entry point for running the pipeline
├── tests/
├── data/                         # SQLite DB and any local artifacts (gitignored)
└── docs/
    └── requirements/
        └── PHASE_1_KNOWLEDGE_ACQUISITION.md
```

### 5.3 Data Model (Conceptual)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CrawlRun    │     │    Document      │     │    Chunk     │
├──────────────┤     ├──────────────────┤     ├──────────────┤
│ id           │────<│ id               │────<│ id           │
│ started_at   │     │ crawl_run_id     │     │ document_id  │
│ completed_at │     │ source_url       │     │ chunk_index  │
│ status       │     │ title            │     │ content      │
│ summary_json │     │ content_type     │     │ heading_path │
│              │     │ raw_content      │     │ token_count  │
│              │     │ content_hash     │     │ content_hash │
│              │     │ retrieved_at     │     │ metadata     │
│              │     │ last_modified    │     │              │
└──────────────┘     └──────────────────┘     └──────────────┘
```

### 5.4 Pipeline Flow

```
[1. Configure]  →  Read scraper.yaml (target URLs, scope rules, rate limits)
       │
[2. Discover]   →  Crawl seed URL(s), follow in-scope links, catalog PDF URLs
       │
[3. Fetch]      →  Render HTML pages (Playwright), download PDFs
       │
[4. Extract]    →  Parse rendered DOM / Parse PDF text with structure
       │
[5. Clean]      →  Strip boilerplate, normalize whitespace, preserve semantics
       │
[6. Chunk]      →  Split into retrieval-ready segments with overlap
       │
[7. Store]      →  Upsert documents and chunks into SQLite (hash-based dedup)
       │
[8. Report]     →  Generate run manifest (counts, changes, errors)
```

---

## 6. Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| All in-scope HTML pages are successfully scraped and stored | Run manifest shows 0 failed pages for in-scope URLs |
| All in-scope PDF documents are extracted and stored | Run manifest shows 0 failed PDFs for discovered documents |
| Every stored chunk has complete provenance metadata | Automated validation query confirms no NULL provenance fields |
| Content is semantically chunked at appropriate granularity | Manual spot-check of 10 random chunks confirms coherent, self-contained content |
| Re-running the pipeline on unchanged content produces no new records | Idempotency test passes with 0 new inserts on second run |
| Pipeline completes within 15 minutes | Timed execution on dev machine |
| Test suite passes with >80% code coverage on core modules | pytest + coverage report |

---

## 7. Phase Boundary & Forward-Looking Considerations

Phase 1 deliberately stops at structured storage. The following concerns are **acknowledged but deferred**:

| Concern | Deferred To | Phase 1 Preparation |
|---------|-------------|---------------------|
| Vector embeddings for semantic search | Phase 2 | Chunk schema includes a nullable `embedding` column |
| LLM integration for answer generation | Phase 2 | Chunk metadata supports source attribution for citations |
| Web application (Reflex full-stack) and chat UI | Phase 3 | Reflex selected; scraper and RAG modules are framework-agnostic Python that Reflex state handlers import |
| Content freshness automation (scheduled re-scrapes) | Phase 5 | Pipeline is idempotent and diff-aware |
| Multi-turn conversation memory | Phase 5 | Single-turn Q&A is sufficient for MVP; conversation memory is a UX enhancement |
| Multi-language support | Future | Storage schema supports a `language` field |
| Additional CRD content domains (housing, etc.) | Future | Scope rules are config-driven, not hardcoded |
| Legal disclaimers and user-facing caveats | Phase 3 | Provenance metadata enables "sourced from [URL] on [date]" attribution |

---

## 8. Detailed Implementation Roadmap

The following is a comprehensive, ordered todo list across all project phases. Each task is sequenced so that dependencies flow top-down within a phase and phase-over-phase. Tasks marked with `[GATE]` are approval/validation checkpoints — work should not proceed past a gate until it is satisfied.

**Design principles applied to this roadmap:**
- **Tests are built into every implementation task** — not listed separately. The deliverable for every "Implement X" task is working code with passing tests.
- **Security is built in** at the point where vulnerable code is written — not bolted on in a late phase.
- **No premature abstraction** — write concrete implementations; refactor if/when a second implementation is actually needed.
- **Parallel tracks** where modules are independent — sequential only where true data dependencies exist.
- **Micro-tasks absorbed** — hash utilities, single-line config entries, and metadata capture are part of their parent tasks, not standalone items.

---

### Phase 1: Knowledge Repository Acquisition

#### 1A — Project Scaffolding & Toolchain

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1A.1 | Initialize git repository, `.gitignore` (with `data/`, `.env`, `__pycache__/`, `*.db`), and `.env.example` template for secrets management from day one | — | `.git/`, `.gitignore`, `.env.example` |
| 1A.2 | Create `pyproject.toml` with project metadata, Python 3.12+ constraint, dependency groups (scraper, dev, test), and pytest configuration (test paths, coverage targets) | — | `pyproject.toml` |
| 1A.3 | Set up `uv` virtual environment, install core dependencies (`playwright`, `beautifulsoup4`, `pdfplumber`, `structlog`, `pyyaml`, `pytest`, `pytest-cov`), install Playwright Chromium binary | 1A.2 | `uv.lock`, working venv, Chromium binary available |
| 1A.4 | Create directory structure per Section 5.2 with `__init__.py` files | 1A.2 | Skeleton project structure |
| 1A.5 | **[GATE]** Verify: `uv run pytest` executes (even with 0 tests), Playwright launches headless Chromium | 1A.1–1A.4 | Green CI-ready baseline |

#### 1B — Technical Spike (Risk Reduction)

> **Purpose:** Validate the three hardest technical unknowns with a throwaway script *before* committing to the full architecture. If any of these fail, the Phase 1 design changes.

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1B.1 | Spike: Use Playwright to render the CRD `/employment/` page. Can we get the full DOM including Divi-rendered accordion/tab content? Document what CSS selectors isolate the main content area vs. navigation/boilerplate. | 1A.5 | Spike notes: DOM structure findings, content selectors, any rendering issues |
| 1B.2 | Spike: Use pdfplumber to extract text from 2 representative CRD PDFs (one fact sheet, one poster). Evaluate structural fidelity — are headings, lists, and tables preserved? Is multi-column layout handled? | 1A.5 | Spike notes: extraction quality assessment, library suitability verdict |
| 1B.3 | **[GATE]** Spike results confirm Playwright + pdfplumber approach is viable, or document alternative approach if not | 1B.1–1B.2 | Technical approach validated (spike code discarded) |

> **1B runs in parallel with 1C. Both tracks can start immediately after 1A.**

---

The following three tracks **(1C, 1D, 1E)** are independent modules that can be developed **in parallel**. They converge at the pipeline orchestration step (1F).

```
1A (scaffolding) → 1B (spike, parallel with 1C)
                 ↘
                   1C (storage)  ──────────┐
                   1D (crawler + extraction) ──→ 1F (pipeline) → 1G (validation)
                   1E (cleaning + chunking) ──┘
```

#### 1C — Storage Layer

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1C.1 | Define data models as Python dataclasses: `CrawlRun`, `Document`, `Chunk` — per Section 5.3 schema, including nullable `embedding` column for future use and `language` field | 1A.4 | `src/employee_help/storage/models.py` |
| 1C.2 | Implement `storage.py` as a SQLite module: DDL for all three tables (with indexes on `content_hash`, `source_url`), functions for `create_run()`, `upsert_document()`, `upsert_chunk()`, `get_document_by_hash()`, `get_run_summary()`. Upsert logic uses content hash comparison for idempotency. Include tests: insert + retrieve round-trip, upsert idempotency (same hash = no new row), run summary accuracy. | 1C.1 | `src/employee_help/storage/storage.py`, `tests/test_storage.py` — all tests passing |
| 1C.3 | **[GATE]** All storage tests pass; idempotency behavior confirmed | 1C.1–1C.2 | Validated storage layer |

#### 1D — Crawler & Content Extraction

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1D.1 | Implement `crawler.py`: accept seed URL(s), launch Playwright headless browser, render page, extract all `<a href>` links from rendered DOM. Implement URL scope filtering (allowlist/blocklist patterns from config, classify as `in_scope` / `out_of_scope` / `pdf_download`). Implement crawl loop with visited-set deduplication and configurable rate limiting. Structured log entry for every URL (status, classification, timing). Include tests: URL scope filtering (allowlist match, blocklist reject, PDF detection, edge cases with fragments/query params/relative URLs). | 1A.5, 1B.3 | `src/employee_help/scraper/crawler.py`, `tests/test_crawler.py` — all tests passing |
| 1D.2 | Implement `extractors/html.py`: receive rendered page HTML, extract main content area (using selectors validated in spike), strip navigation/header/footer/sidebar/cookie banners, preserve heading hierarchy (`h1`–`h6`), lists, emphasis, and paragraph structure; capture metadata (page title, headings list, content length, source URL, retrieval timestamp, HTTP last-modified); output structured Markdown. Include tests with sample Divi-themed HTML fixture. | 1B.3 | `src/employee_help/scraper/extractors/html.py`, `tests/test_html_extractor.py` — all tests passing |
| 1D.3 | Implement `extractors/pdf.py`: download PDF from URL, extract text with `pdfplumber` preserving structure (headings, body, lists, tables); handle multi-column layouts; capture metadata (document title, headings list, content length, source URL, retrieval timestamp); output structured Markdown. Include tests with a sample PDF fixture. | 1B.3 | `src/employee_help/scraper/extractors/pdf.py`, `tests/test_pdf_extractor.py` — all tests passing |
| 1D.4 | Manual QA: run HTML extractor against live CRD `/employment/` page and PDF extractor against 3 representative CRD fact sheets. Compare output to manually observed content. Document any gaps. | 1D.2, 1D.3 | QA notes documenting extraction fidelity |
| 1D.5 | **[GATE]** Crawler discovers the known content inventory from Section 2.3 with no out-of-scope URL leaks. Extraction output for both HTML and PDF is clean, structured, and content-complete per manual QA. | 1D.1–1D.4 | Validated crawler & extraction layer |

#### 1E — Content Processing (Cleaning & Chunking)

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1E.1 | Implement `cleaner.py`: normalize whitespace, remove duplicate blank lines, fix encoding artifacts, strip residual boilerplate (e.g., "Skip to content" text, breadcrumb trails), standardize heading markers. Include tests: whitespace normalization, boilerplate removal, encoding fix. | 1A.4 | `src/employee_help/processing/cleaner.py`, `tests/test_cleaner.py` — all tests passing |
| 1E.2 | Implement `chunker.py`: split cleaned content into chunks of 500–1500 tokens; respect section boundaries (never split mid-section if section fits in one chunk); apply configurable overlap (default: 100 tokens); attach heading path context to each chunk (e.g., "Employment > Protected Categories > Disability"); generate deterministic SHA-256 content hash per chunk for deduplication. Include tests: chunk size bounds, overlap presence, section boundary respect, heading path propagation, hash determinism. | 1E.1 | `src/employee_help/processing/chunker.py`, `tests/test_chunker.py` — all tests passing |
| 1E.3 | **[GATE]** 10 sample chunks from real CRD content are coherent, self-contained, and carry correct heading paths | 1E.1–1E.2 | Validated processing layer |

#### 1F — Pipeline Orchestration & CLI

> **This is the convergence point.** All three parallel tracks (1C, 1D, 1E) must be validated before pipeline integration.

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1F.1 | Implement `scraper.yaml` configuration: seed URLs, URL allowlist/blocklist patterns, rate limit settings, chunk size parameters, output paths. Implement `config.py` to load and validate YAML, expose as typed dataclass. | 1A.4 | `config/scraper.yaml`, `src/employee_help/scraper/config.py` |
| 1F.2 | Implement `pipeline.py`: orchestrate full flow — load config → init storage → create crawl run → crawl → extract → clean → chunk → store → generate run manifest (pages crawled, PDFs processed, chunks created, documents unchanged/updated, errors with failed URLs). Handle errors per-document (log and continue, don't abort entire run). Include integration test: full pipeline run against cached fixtures, verify DB populated correctly. | 1C.3, 1D.5, 1E.3, 1F.1 | `src/employee_help/scraper/pipeline.py`, `tests/test_pipeline_integration.py` |
| 1F.3 | Implement `cli.py`: CLI entry point with `[project.scripts]` registration in `pyproject.toml`; invocable as `employee-help scrape`. | 1F.2 | `src/employee_help/cli.py`, updated `pyproject.toml` |
| 1F.4 | **[GATE]** Full pipeline runs end-to-end via CLI, DB contains expected documents and chunks, manifest reports zero errors for in-scope content | 1F.1–1F.3 | Pipeline operational |

#### 1G — Phase 1 Validation & Acceptance

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 1G.1 | Run full pipeline against live CRD site + idempotency re-run (second execution with unchanged content produces zero new inserts) | 1F.4 | Populated SQLite database; idempotency confirmed |
| 1G.2 | Manual review: query DB, read 10 random chunks, confirm coherence, self-containment, and provenance accuracy. Verify `pytest --cov` shows >80% coverage on core modules. | 1G.1 | PO spot-check sign-off |
| 1G.3 | **[GATE]** Product Owner approves Phase 1 output; knowledge base is accepted as foundation for Phase 2 | 1G.1–1G.2 | **Phase 1 accepted** |

---

### Phase 2: RAG Pipeline & Answer Generation

#### 2A — Embedding & Semantic Search

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 2A.1 | Evaluate and select embedding model and vector search approach as a single decision. Candidates — embedding: OpenAI `text-embedding-3-small`, Sentence Transformers local model, Anthropic embeddings; search: SQLite + numpy cosine similarity (simple), ChromaDB, or Qdrant. Consider cost, latency, quality, data privacy, and operational complexity. | Phase 1 accepted | ADR documenting both choices together |
| 2A.2 | Implement embedding generation: batch-process all chunks through selected embedding model, store vectors. Implement semantic search service: accept query text → embed query → find top-K similar chunks → return ranked results with metadata. Include tests for search quality: known questions with expected relevant chunks, measure recall@5 and recall@10. | 2A.1 | `src/employee_help/search/`, `tests/test_search.py`, quality benchmark |
| 2A.3 | **[GATE]** Search returns relevant chunks for 20+ representative user questions with acceptable recall. If recall is insufficient, add metadata-filtered hybrid search (combine semantic similarity with content type / topic filters) and re-test. | 2A.2 | Validated search layer |

#### 2B — LLM Integration & Answer Generation

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 2B.1 | Select LLM provider and model for answer generation (candidates: Anthropic Claude, OpenAI GPT-4o) — consider accuracy on legal content, cost, context window, and API terms | Phase 1 accepted | ADR documenting choice |
| 2B.2 | Design and implement RAG answer generation service: prompt template with role definition (legal information assistant, not a lawyer), retrieved context injection, source attribution instructions (each answer references specific CRD sources with URLs and retrieval dates), legal disclaimer injection ("This is informational only, not legal advice..."), response format guidelines. Include prompt injection defenses in the system prompt design. Receive user query → retrieve relevant chunks (2A) → assemble prompt → call LLM → parse response with citations. Include tests with sample inputs. | 2B.1, 2A.3 | `src/employee_help/chat/rag.py`, `tests/test_rag.py`, prompt template |
| 2B.3 | Quality evaluation: 20+ question-answer pairs manually graded for accuracy, relevance, appropriate sourcing, and disclaimer presence | 2B.2 | `tests/test_rag_quality.py`, evaluation report |
| 2B.4 | **[GATE]** RAG answers are accurate, well-sourced, and appropriately disclaimed for 20+ test questions | 2B.1–2B.3 | Validated RAG pipeline |

> **Note:** 2A and 2B.1 (LLM selection) can proceed in parallel — the LLM choice doesn't depend on search validation.

---

### Phase 3: Web Application (Reflex Full-Stack)

> Reflex serves as both frontend and backend in a single process. The RAG service (Phase 2) integrates as a Python module that Reflex state handlers call directly — no separate API server needed.

#### 3A — Application Shell & Backend Integration

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3A.1 | Initialize Reflex project within the existing `employee_help` structure. Create Reflex state class that wraps the RAG service (2B) — state handlers accept user messages, call the RAG module, and return answers with sources. | 2B.4 | Reflex app skeleton with RAG integration |
| 3A.2 | Design and implement page layout with accessibility built in from the start: responsive shell with header (branding, persistent non-dismissible "This is not legal advice" disclaimer banner), main content area, footer (attribution, links). Theme: professional, accessible, WCAG 2.1 AA compliant color contrast and typography. | 3A.1 | Base layout component with theme |
| 3A.3 | Implement landing page: value proposition, scope of advice available, prominent disclaimer, "Start a conversation" CTA, 3–4 suggested starter questions | 3A.2 | Landing page |

#### 3B — Chat Interface

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3B.1 | Implement chat message components: user message bubble, assistant message bubble (with Markdown rendering), typing/loading indicator, error state display. Include source citation rendering: clickable source links below each answer showing document title and "as of" date. | 3A.2 | Chat UI components |
| 3B.2 | Implement chat input with built-in input validation: text area with send button, keyboard shortcut (Enter to send), character limit, disabled state while awaiting response, sanitize input before passing to RAG service | 3B.1 | Chat input component |
| 3B.3 | Implement conversation flow: scrollable message list, auto-scroll to latest, "New conversation" action to clear chat and start fresh session | 3B.1 | Conversation state management |

#### 3C — Supporting Pages & Polish

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 3C.1 | Implement "About" page (what this tool is, what it isn't, data sources, limitations, full disclaimer) and "Sources" page (browsable list of all knowledge base documents with links to original CRD pages) | 3A.2 | About page, Sources page |
| 3C.2 | Error handling UX: friendly error messages for service failures, rate limit exceeded, timeouts | 3B.2 | Error state components |
| 3C.3 | Mobile responsiveness pass: verify chat is usable on phone screens, fix any layout issues | 3B.1–3B.3 | Responsive layout verified |
| 3C.4 | **[GATE]** Full end-to-end user flow works: land on home → start chat → ask question → receive sourced answer with disclaimer → view sources page. Works on desktop and mobile. | 3A–3C | **Phase 3 complete** |

---

### Phase 4: Production Readiness & Deployment

#### 4A — Infrastructure & Deployment

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 4A.1 | Create `Dockerfile` and `docker-compose.yaml`: containerized Reflex app with SQLite (or PostgreSQL if expected usage warrants the migration) | Phase 3 | Container configuration |
| 4A.2 | Select hosting platform (candidates: Railway, Fly.io, AWS ECS, self-hosted VPS) — consider cost, simplicity, SSL, scaling | 4A.1 | ADR documenting choice |
| 4A.3 | Configure HTTPS enforcement, security headers (HSTS, CSP, X-Frame-Options), and dependency vulnerability audit (`uv audit` or equivalent) | 4A.1 | Security configuration, clean audit report |
| 4A.4 | Set up CI/CD pipeline: run tests on push, build container, deploy on merge to main | 4A.1, 4A.2 | CI/CD configuration (GitHub Actions or similar) |
| 4A.5 | Set up domain name, SSL certificate, and initial production deployment | 4A.2–4A.4 | App running in production at HTTPS URL |

#### 4B — Monitoring & Operations

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 4B.1 | Implement application health monitoring: uptime check, response time tracking, error rate alerting | 4A.5 | Monitoring configuration |
| 4B.2 | Implement LLM cost tracking: monitor API usage and cost per query — essential for budget management | 4A.5 | Cost tracking |
| 4B.3 | Document runbook: how to re-run scraper, how to deploy, how to roll back, how to monitor, how to check costs | 4A.5 | `docs/runbook.md` |
| 4B.4 | **[GATE]** Application is live, monitored, cost-tracked, and operationally documented | 4A–4B | **Phase 4 complete — MVP launched** |

---

### Phase 5: Iteration & Expansion (Post-MVP)

> All Phase 5 items depend on Phase 4 (working production app). They are **independent of each other** — prioritize based on user feedback and business needs. No sequential dependencies within Phase 5 unless noted.

#### 5A — Content Expansion & Freshness

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 5A.1 | Automate content refresh: scheduled pipeline runs (cron or cloud scheduler) with change-detection notifications | Phase 4 | Automated scrape schedule |
| 5A.2 | Add non-English content support: Spanish-language CRD materials as first additional language | Phase 4 | Multi-language knowledge base |
| 5A.3 | Expand content scope: housing discrimination, hate violence, or other CRD domains as configured | Phase 4 | Broadened knowledge base |
| 5A.4 | Integrate supplementary legal sources: relevant California statutes, case law summaries (requires legal review) | Phase 4 | Enriched knowledge base |

#### 5B — User Experience Enhancements

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 5B.1 | Implement feedback mechanism: thumbs up/down on answers for quality tracking | Phase 4 | Feedback component + storage |
| 5B.2 | Implement answer quality improvement loop: review low-rated answers, adjust prompts and chunking | 5B.1 | Improved answer quality |
| 5B.3 | Implement multi-turn conversation memory: maintain session context for follow-up questions (context window management, relevance decay) | Phase 4 | Conversation memory |
| 5B.4 | Implement topic-guided navigation: let users browse by protected category (age, disability, pregnancy, etc.) before chatting | Phase 4 | Topic browse UI |
| 5B.5 | Implement complaint filing guidance: interactive flow that helps users determine if/how to file a CRD complaint based on their situation | Phase 4 | Guided workflow |

#### 5C — Platform Maturity

| # | Task | Depends On | Deliverable |
|---|------|------------|-------------|
| 5C.1 | Load testing and performance optimization: ensure acceptable response times under concurrent load | Phase 4 | Performance benchmarks |
| 5C.2 | Legal review of disclaimers, terms of service, and privacy policy | Phase 4 | Legal documents |
| 5C.3 | Accessibility compliance certification (WCAG 2.1 AA) | Phase 4 | Compliance report |
| 5C.4 | Usage analytics: anonymized query volume, popular topics, session length — no PII stored (implement only if needed for decision-making) | Phase 4 | Analytics pipeline |
| 5C.5 | Implement admin dashboard: content management, system health, manual content review/override (implement only if operational need emerges) | Phase 4 | Admin UI |

---

### Phase Summary

| Phase | Focus | Key Outcome |
|-------|-------|-------------|
| **Phase 1** | Knowledge Acquisition | Structured, query-ready knowledge base in SQLite |
| **Phase 2** | RAG Pipeline | Working answer generation service with semantic search, source attribution, and disclaimers |
| **Phase 3** | Web Application | User-facing Reflex app with chat interface, sourced answers, and supporting pages |
| **Phase 4** | Production Deployment | Live, monitored, cost-tracked application with CI/CD |
| **Phase 5** | Iteration & Expansion | Content growth, conversation memory, UX refinement, platform maturity — driven by user feedback |

> **Phases 1–4 are the MVP path (~55 tasks).** Phase 5 is a prioritizable backlog. Within each phase, work top-down and respect `[GATE]` checkpoints. Parallel tracks within Phase 1 are explicitly marked.

---

## 9. Product Owner Decisions (Resolved)

| # | Question | Decision | Impact |
|---|----------|----------|--------|
| 1 | Include CRD regulatory text in Phase 1? | **Defer to later phase.** Focus on consumer-facing materials. | Regulatory text (FEHA amendments, rule filings) excluded from Phase 1 scope. Keeps knowledge base focused on plain-language content suited for a chat assistant. |
| 2 | PDF scope: regulatory filings vs. consumer materials? | **Consumer-facing only.** Fact sheets, brochures, posters, employer guides, FAQs. | Dense regulatory PDFs excluded. Scraper scope rules will filter for consumer-oriented documents only. |
| 3 | Content refresh cadence? | **Manual / ad-hoc via CLI.** Run when content is known to have changed (e.g., after annual law updates). | No automated scheduling in any phase. Pipeline stays a CLI tool. Removes infrastructure complexity. |
| 4 | External AI APIs vs. local models? | **External APIs are fine.** Content is public government data — no privacy concern. | Phase 2 can use OpenAI/Anthropic APIs for embeddings and LLM. Simpler architecture, better quality, lower upfront cost. |
| 5 | Hosting preference? | **No preference yet.** Decide at Phase 4. | Architecture stays hosting-agnostic. Evaluate Railway, Fly.io, AWS, etc., when deployment is imminent. |
