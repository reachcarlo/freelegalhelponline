# Employee Help — Functionality Inventory

> **Last updated**: 2026-03-03
> **Platform**: AI-powered California employment rights legal guidance
> **Tech stack**: Python 3.12 / FastAPI / Next.js 16 / SQLite / LanceDB / Claude API

---

## Table of Contents

1. [Knowledge Base Acquisition & Ingestion](#1-knowledge-base-acquisition--ingestion)
2. [RAG Search & Answer Generation](#2-rag-search--answer-generation)
3. [Consumer Assessment Tools](#3-consumer-assessment-tools)
4. [Discovery Document Generation](#4-discovery-document-generation)
5. [Web Application](#5-web-application)
6. [Analytics, Feedback & Quality Assurance](#6-analytics-feedback--quality-assurance)
7. [CLI Tooling](#7-cli-tooling)
8. [Cross-Product Integration Map](#8-cross-product-integration-map)
9. [Test Suite Summary](#9-test-suite-summary)

---

## 1. Knowledge Base Acquisition & Ingestion

### What It Does

Multi-source pipeline that acquires, processes, and stores California employment law content from 21 sources across 5 source types: statutory codes (via PUBINFO database), agency websites (via Playwright crawler), regulatory codes (via Cornell LII), case law (via CourtListener API), and specialized PDFs (CACI jury instructions, DLSE manuals/opinions).

### User

Both (consumer and attorney). Content is ingested uniformly; mode-based filtering happens at retrieval time.

### Use Case

Build and maintain a comprehensive, up-to-date knowledge base of California employment law so that the RAG system can retrieve authoritative, citable content for both consumers and attorneys.

### Knowledge Sources (21 total)

#### Statutory Codes — 9 sources (PUBINFO loader)

| Source | Code | Divisions | Documents | Chunks |
|--------|------|-----------|-----------|--------|
| California Labor Code | LAB | All 7 | 2,631 | 2,733 |
| Gov Code — FEHA | GOV | Division 3 | 4,649 | 4,718 |
| Gov Code — Whistleblower | GOV | Divisions 1–2 | 7,772 | 7,980 |
| Unemployment Insurance Code | UIC | Division 1 | 838 | 850 |
| Business & Professions Code | BPC | Division 7 | 475 | 492 |
| Code of Civil Procedure | CCP | All | 3,411 | 3,447 |
| Health & Safety Code | HSC | Division 5 | — | — |
| Education Code | EDC | Division 4 | — | — |
| Civil Code | CIV | Divisions 1, 3 | — | — |

#### Regulatory Codes — 2 sources (Cornell LII scraper)

| Source | Code | Scope | Content Category |
|--------|------|-------|------------------|
| CCR Title 2 FEHA Regulations | 2-CCR | 80 sections, 11 articles | `regulation` |
| CCR Title 8 Industrial Relations | 8-CCR | Division 1 (wage/hour/safety) | `regulation` |

#### Agency Websites — 4 sources (Playwright crawler)

| Source | Max Pages | Documents | Chunks | Errors |
|--------|-----------|-----------|--------|--------|
| DIR/DLSE | 300 | 270 | 1,757 | 30 |
| EDD | 200 | 200 | 411 | 0 |
| CalHR | 300 | 300 | 1,365 | 0 |
| CRD (Civil Rights Dept) | 100 | — | — | — |

#### Federal & External — 2 sources (Playwright crawler)

| Source | Max Pages | Purpose |
|--------|-----------|---------|
| EEOC Guidance | 150 | Federal Title VII, ADA, ADEA |
| Legal Aid at Work | 150 | Plain-language fact sheets |

#### Specialized PDF/Document Sources — 3 sources

| Source | Method | Documents | Chunks | Content Category |
|--------|--------|-----------|--------|------------------|
| CACI Jury Instructions | PDF parse (pdfplumber) | 325 | 353 | `jury_instruction` |
| DLSE Opinion Letters | Web index + PDF download | — | — | `opinion_letter` |
| DLSE Enforcement Manual | PDF parse | — | — | `enforcement_manual` |

#### Case Law — 1 source (CourtListener API)

| Source | Courts | Max Opinions | Filed After | Content Category |
|--------|--------|-------------|-------------|------------------|
| CourtListener | CA Supreme + Courts of Appeal | 5,000 | 1990 | `case_law` |

### Features

- **PUBINFO Loader** (primary statutory source): Parses 677 MB ZIP archive of tab-delimited `.dat` files with HTML LOB sidecars. Handles 185,713 LOB files, filters by code abbreviation + target divisions.
- **Statutory Web Scraper** (fallback): httpx-based scraper for leginfo.legislature.ca.gov with 3x exponential backoff retry + circuit breaker (>50% failure threshold). Rate-limited per robots.txt.
- **Agency Crawler**: Playwright-based with configurable seed URLs, allowlist/blocklist regex, rate limiting (2–10s), and content-type-specific extraction (HTML via BeautifulSoup → Markdown, PDF via pdfplumber).
- **CACI Loader**: Parses 3,560-page Judicial Council PDF. Extracts 110 instructions across 6 employment series (2400–4699) with per-section chunking (instruction text, directions for use, sources and authority).
- **CCR Loaders**: Fetches California Code of Regulations from Cornell LII. Title 2 uses hardcoded 80-section manifest; Title 8 crawls TOC hierarchy to discover sections.
- **CourtListener Integration**: Paginated API client with auth, rate limit 429 handling, retry with backoff. Filters by 10 employment-specific search queries. Eyecite citation extraction + employment relevance scoring.
- **DLSE Loaders**: Opinion letters (two-phase: index scrape → PDF download, 1983–2019). Enforcement manual (352-page PDF with chapter detection).
- **Idempotency**: Content-hash-based change detection. `upsert_document()` skips unchanged content. Pipeline checks `is_new` flag before inserting chunks.
- **Soft-delete**: `is_active` boolean on chunks for repealed section handling. `deactivate_missing_sections()` marks obsolete sections.
- **Resumability**: Statutory extractor tracks `completed_urls` for interrupted runs.
- **Content cleaning**: Unicode normalization, mojibake fixing, boilerplate removal (per-source patterns), whitespace normalization.

### Chunking Strategies

| Strategy | Used For | Min Tokens | Max Tokens | Overlap |
|----------|----------|------------|------------|---------|
| `heading_based` | Agency pages | 200 | 1,500 | 100 |
| `section_boundary` | Statutory codes | 50 | 2,000 | 0 |
| `case_law` | Court opinions | — | 1,500 | 100 |

### Key Files

- Pipeline: `src/employee_help/pipeline.py`
- Source configs: `config/sources/*.yaml` (21 files)
- PUBINFO loader: `src/employee_help/scraper/extractors/pubinfo.py`
- Statute web scraper: `src/employee_help/scraper/extractors/statute.py`
- CACI loader: `src/employee_help/scraper/extractors/caci.py`
- CCR loaders: `src/employee_help/scraper/extractors/ccr.py`, `ccr_title8.py`
- DLSE loaders: `src/employee_help/scraper/extractors/dlse_opinions.py`, `dlse_manual.py`
- Opinion loader: `src/employee_help/scraper/extractors/opinion_loader.py`
- CourtListener client: `src/employee_help/scraper/extractors/courtlistener.py`
- HTML extractor: `src/employee_help/scraper/extractors/html.py`
- PDF extractor: `src/employee_help/scraper/extractors/pdf.py`
- Chunker: `src/employee_help/processing/chunker.py`
- Cleaner: `src/employee_help/processing/cleaner.py`
- Citation extractor: `src/employee_help/processing/citation_extractor.py`
- Storage: `src/employee_help/storage/storage.py`
- Models: `src/employee_help/storage/models.py`

### Test Suite

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_pubinfo_loader.py` | ~25 | PUBINFO parsing, LOB resolution, filtering |
| `test_statute_extractor.py` | — | Web scraper extraction, TOC parsing |
| `test_statute_pipeline.py` | — | Scraper resilience, retry, circuit breaker |
| `test_web_scraper_resilience.py` | — | Proxy errors, fallback behavior |
| `test_caci_loader.py` | ~40 | PDF parsing, series filtering, section extraction |
| `test_ccr.py` | — | CCR Title 2 FEHA regulation scraping |
| `test_ccr_title8.py` | — | CCR Title 8 regulation scraping |
| `test_dlse_opinions.py` | — | Opinion letter index + PDF download |
| `test_dlse_manual.py` | — | Enforcement manual PDF parsing |
| `test_courtlistener.py` | ~43 | API auth, pagination, rate limit, retry |
| `test_opinion_loader.py` | ~38 | Employment signal detection, filtering |
| `test_crawler.py` | — | URL classification, Playwright crawling |
| `test_html_extractor.py` | — | HTML → Markdown extraction |
| `test_pdf_extractor.py` | — | PDF → text extraction |
| `test_chunker.py` | — | All chunking strategies |
| `test_case_law_chunker.py` | ~23 | Case law segmentation, citation headers |
| `test_cleaner.py` | — | Unicode, boilerplate, whitespace |
| `test_citation_extractor.py` | ~40 | Eyecite wrapper, CA filtering |
| `test_citation_regression.py` | — | Golden dataset regression |
| `test_citation_links.py` | ~23 | Bidirectional linking, dedup |
| `test_pipeline.py` | — | Pipeline routing, orchestration |
| `test_caselaw_pipeline.py` | ~21 | Case law ingest, chunk storage |
| `test_statutory_pipeline.py` | — | Statutory features, resumability |
| `test_refresh.py` | — | Change detection, content hash |
| `test_storage.py` | — | SQLite operations, schema |
| `test_config.py` | — | YAML config loading |
| `test_source_registry.py` | — | Source model validation |

---

## 2. RAG Search & Answer Generation

### What It Does

Dual-mode retrieval-augmented generation system that answers California employment law questions. Retrieves relevant chunks via hybrid search (dense vectors + BM25), builds Claude API prompts with Citations API document blocks, and streams answers with verified citations.

### User

Both — with distinct behavior per mode.

| Aspect | Consumer Mode | Attorney Mode |
|--------|--------------|---------------|
| LLM | Claude Haiku 4.5 (~$0.006/query) | Claude Sonnet 4.6 (~$0.032/query) |
| Tone | Warm, conversational, college reading level | Professional, 3rd-year associate level |
| Content filters | Agency guidance, fact sheets, FAQs, opinions, regulations | All sources (statutory, case law, jury instructions, regulations) |
| Turn limit | 3 turns per conversation | 5 turns per conversation |
| Response format | Short Answer → What You Should Know → Next Steps → Questions | tl;dr → Short Answer → Analysis → Follow-up Questions |
| Citation verification | No | Yes (case law + statute verification) |
| Boosts | — | Statutory 1.2x, CACI 1.3x, case law 1.25x, citation 2–4x |

### Use Case

- **Consumer**: Employee with no legal training seeking to understand their rights, next steps, and which agencies to contact.
- **Attorney**: Licensed attorney researching California employment law, needing statutory citations, case law analysis, and procedural guidance.

### Features

#### Retrieval Pipeline
1. **Query preprocessing**: Citation detection (regex for Cal. Lab. Code, Gov. Code, etc.), legal term expansion (FEHA, CFRA, DLSE → full names), whitespace normalization.
2. **Embedding**: BGE-base-en-v1.5 (768-dim, 512 max seq len). Asymmetric — queries use retrieval instruction prefix. ~3.1 chunks/sec on CPU.
3. **Hybrid search**: LanceDB vector similarity + BM25 (FTS index) combined via Reciprocal Rank Fusion (RRF, k=60). Content column prepends `[citation] heading_path\n` for BM25 discoverability.
4. **Mode filtering**: Consumer restricts to `{agency_guidance, fact_sheet, faq, opinion_letter, enforcement_manual, federal_guidance, legal_aid_resource, regulation}`. Attorney includes all + statutory boost.
5. **Reranker** (optional, disabled by default): mxbai-rerank-base-v2 cross-encoder. 70% reranker + 30% hybrid score blending. Disabled on macOS x86_64 due to OOM.
6. **Deduplication**: Content-hash dedup + source diversity enforcement (max 3 chunks per document).
7. **Configuration**: top_k_search=50, top_k_rerank=10, top_k_final=5.

#### Generation Pipeline
1. **Prompt building**: Jinja2 templates (`consumer_system.j2`, `attorney_system.j2`). Token budget fitting (6,000 tokens for context). Citations API document blocks with metadata headers.
2. **Streaming**: SSE protocol — sources emitted immediately, then token-by-token streaming, then done event with metadata.
3. **Citations API**: Each chunk becomes a document block. Claude returns document_index + char_locations. Mapped back to source chunks for attribution.
4. **Citation validation**: Strict mode (remove unverified) or permissive (mark `[unverified]`). Checks section number + code type (Lab vs Gov vs Bus) to prevent cross-code false matches.
5. **Multi-turn conversation**: Client-side history, server-side turn enforcement. History token budget: 2,000. Short follow-up expansion (<6 words → expand with original question for better retrieval).

#### Citation Verification (Attorney Mode)
- **Case citations**: Extracted via Eyecite → looked up on CourtListener API → verified (exists, California jurisdiction, year match). Statuses: VERIFIED, NOT_FOUND, WRONG_JURISDICTION, DATE_MISMATCH, AMBIGUOUS.
- **Statute citations**: Extracted via Eyecite → looked up in local DB → verified (exists, is_active, ingestion recency <30 days). Statuses: VERIFIED, NOT_FOUND, REPEALED, AMENDED.
- **Confidence scoring**: VERIFIED (green) / UNVERIFIED (yellow) / SUSPICIOUS (red).

### Knowledge Sources

All 21 sources from Section 1, filtered by mode at retrieval time.

### Key Files

- Retrieval service: `src/employee_help/retrieval/service.py`
- Embedder: `src/employee_help/retrieval/embedder.py`
- Vector store: `src/employee_help/retrieval/vector_store.py`
- Query preprocessor: `src/employee_help/retrieval/query.py`
- Reranker: `src/employee_help/retrieval/reranker.py`
- LLM client: `src/employee_help/generation/llm.py`
- Prompt builder: `src/employee_help/generation/prompts.py`
- Answer service: `src/employee_help/generation/service.py`
- Citation verifier: `src/employee_help/generation/citation_verifier.py`
- Generation models: `src/employee_help/generation/models.py`
- Prompt templates: `config/prompts/consumer_system.j2`, `attorney_system.j2`
- RAG config: `config/rag.yaml`

### Test Suite

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_embedder.py` | — | Embedding service, BGE model |
| `test_embedding_integration.py` | — | Real model integration (slow marker) |
| `test_vector_store.py` | — | LanceDB operations, hybrid search |
| `test_retrieval_service.py` | — | Mode filtering, scoring, dedup, diversity |
| `test_reranker.py` | — | Cross-encoder scoring, blending |
| `test_query_preprocessor.py` | — | Citation detection, term expansion |
| `test_llm_client.py` | — | Claude API wrapper, Citations API |
| `test_generation.py` | — | Answer generation pipeline |
| `test_answer_service.py` | — | Full RAG orchestration |
| `test_answer_models.py` | — | TokenUsage, cost estimation |
| `test_prompt_builder.py` | — | Jinja2 rendering, document blocks |
| `test_citation_verifier.py` | ~59 | Case + statute verification, confidence |
| `test_case_law_retrieval.py` | ~15 | Attorney includes, consumer excludes |
| Evaluation: `test_retrieval_quality.py` | — | Precision, recall, MRR metrics |
| Evaluation: `test_citation_integrity.py` | — | No hallucinated citations |

---

## 3. Consumer Assessment Tools

### What It Does

Five stateless, calculator-style tools that help California employees understand their rights, compute damages, identify filing deadlines, and get routed to the correct government agency — all without requiring LLM calls (except the intake summary).

### User

Consumer only.

### Use Case

Self-service employment rights assessment. Employees can quickly determine their situation, calculate what they may be owed, identify deadlines, and know where to file complaints — before or instead of consulting an attorney.

---

### Tool 1: Statute of Limitations Calculator

**What it does**: Computes all relevant filing deadlines for a given employment claim type and incident date.

**Input**: Claim type (8 types: FEHA discrimination, wage theft, wrongful termination, retaliation/whistleblower, PAGA, CFRA family leave, government employee, misclassification) + incident date.

**Output**: List of deadlines with urgency classification (expired/critical <30d/urgent <90d/normal), filing entity, legal citation, and portal URL.

**Example**: FEHA discrimination with incident 2025-06-01 → CRD complaint (3 years), EEOC charge (300 days), civil suit (1 year after right-to-sue).

**Key files**: `src/employee_help/tools/deadlines.py`
**API endpoint**: `POST /api/deadlines`
**Tests**: `test_deadlines.py`, `test_deadlines_api.py`

---

### Tool 2: Unpaid Wages Calculator

**What it does**: Computes total wage damages including unpaid wages, meal/rest break premiums, waiting time penalties, and prejudgment interest — with legal citations for each line item.

**Input**: Hourly rate, unpaid hours, employment status, termination date, final wages paid date, missed meal/rest breaks, unpaid since date.

**Output**: Itemized breakdown with amounts and citations (Lab. Code sections 200–204, 226.7(c), 203, 1671).

**Calculations**:
- Unpaid wages: rate x hours
- Meal break premiums: 1 hour x rate per violation
- Rest break premiums: 1 hour x rate per violation
- Waiting time penalties: 8 x rate x days late (capped at 30 days)
- Prejudgment interest: simple interest from unpaid_since to present

**Key files**: `src/employee_help/tools/unpaid_wages.py`
**API endpoint**: `POST /api/unpaid-wages`
**Tests**: `test_unpaid_wages.py` (~45 tests), `test_unpaid_wages_api.py`

---

### Tool 3: Agency Routing Guide

**What it does**: Recommends the correct government agencies for filing complaints based on issue type and employment sector, with priority ranking.

**Input**: Issue type (13 types: unpaid wages, discrimination, harassment, wrongful termination, retaliation, CFRA, workplace safety, misclassification, unemployment, disability insurance, paid family leave, meal/rest breaks, whistleblower) + government employee flag.

**Output**: Priority-ranked agency list (prerequisite → primary → alternative) with name, acronym, portal URL, phone, filing methods, process overview, typical timeline.

**Agencies covered**: DLSE, CRD, EEOC, DIR, EDD, Cal/OSHA.

**Key files**: `src/employee_help/tools/routing.py`
**API endpoint**: `POST /api/agency-routing`
**Tests**: `test_routing.py`, `test_routing_api.py`

---

### Tool 4: Guided Intake Questionnaire

**What it does**: Multi-question branching interview that identifies employment issues, recommends relevant tools with pre-filled parameters, and optionally streams a personalized AI rights summary.

**Input**: Answers to 8 branching questions (situation, pay details, unfair treatment details, retaliation flag, reporting details, employment status, employer type, benefits needed).

**Output**: Identified issues with confidence levels (high/medium), tool recommendations with pre-filled params, deadline urgency flags, and optional streaming rights summary via RAG.

**Features**:
- Conditional question visibility (branching logic via `show_if`)
- Issue scoring with confidence levels
- Tool recommendations with pre-fill parameters (e.g., claim_type for deadline calculator)
- `build_intake_query()` converts identified issues → natural language RAG query
- Streaming rights summary via `/api/intake-summary` endpoint

**Key files**: `src/employee_help/tools/intake.py`
**API endpoints**: `GET /api/intake-questions`, `POST /api/intake`, `POST /api/intake-summary` (SSE)
**Tests**: `test_intake.py` (~45 tests), `test_intake_api.py`, `test_intake_summary_api.py` (7 tests)

---

### Tool 5: Incident Documentation Guide

**What it does**: Provides structured guidance for documenting workplace incidents, including evidence checklists and legal tips.

**Input**: Incident type (7 types: discrimination, harassment, wrongful termination, retaliation, wage theft, safety violation, family leave denial).

**Output**: Common fields (date, location, witnesses), incident-specific fields, documentation prompts, evidence checklist (critical/high/useful importance), related claim types, legal tips.

**Key files**: `src/employee_help/tools/incident_docs.py`
**API endpoint**: `POST /api/incident-guide`
**Tests**: `test_incident_docs.py`, `test_incident_docs_api.py`

---

### Cross-Tool Integration

The Guided Intake acts as a **hub**: it identifies issues, then recommends the other tools with pre-filled parameters. For example:
- Unpaid wages identified → recommends Unpaid Wages Calculator (pre-fills employment_status)
- Discrimination identified → recommends Deadline Calculator (pre-fills claim_type=feha_discrimination) + Agency Routing (pre-fills issue_type=discrimination)
- Any issue → recommends Incident Documentation Guide (pre-fills incident_type)

---

## 4. Discovery Document Generation

### What It Does

Generates California-compliant litigation discovery documents: Form Interrogatories (DISC-001/002 PDFs), Special Interrogatories (SROGs), Requests for Production (RFPDs), Requests for Admission (RFAs), and Proof of Service (POS) — all on proper pleading paper with correct formatting.

### User

Attorney only. Discovery documents are legal filings that require attorney oversight.

### Use Case

Employment litigation attorneys can quickly assemble discovery sets by selecting from curated request banks (organized by claim type), adding custom requests, and generating court-ready documents. Reduces document preparation time from hours to minutes.

### Features

#### Document Types

| Document | Format | Template | Limit | Standard |
|----------|--------|----------|-------|----------|
| DISC-001 (Form Interrogatories — General) | PDF fill | Judicial Council form | 180 sections | CCP §2030.010 |
| DISC-002 (Form Interrogatories — Employment) | PDF fill | Judicial Council form | 91 sections | CCP §2030.010 |
| Special Interrogatories (SROGs) | DOCX | 28-line pleading paper | 35 without declaration | CCP §2030.030 |
| Requests for Production (RFPDs) | DOCX | 28-line pleading paper | No limit | CCP §2031.010 |
| Requests for Admission (RFAs) | DOCX | 28-line pleading paper | 35 fact/mixed | CCP §2033.030 |
| Proof of Service (POS) | DOCX | 28-line pleading paper | — | CCP §1013/1010.6 |

#### Request Banks

- **SROGs**: 58 role-aware interrogatories across 16 categories (plaintiff, defendant, shared)
- **RFPDs**: 52 role-aware document requests across 24 categories
- **RFAs**: 67 role-aware requests for admission across 17 categories (60 fact + 7 genuineness)

> Variable substitution ({EMPLOYEE}, {EMPLOYER}, etc.) adapts request text to case context. Role and claim filtering ensures only relevant requests surface.
- **FROGs General**: 180 sections across 13 categories
- **FROGs Employment**: 91 sections across employment-specific categories

#### Wizard Flow (frontend)

1. **Case Info**: Case number, court county, party role, plaintiffs/defendants, attorney info (name, SBN, address, firm, pro per flag), court details, set number
2. **Claim Types**: Multi-select from 19 employment claim types
3. **Request Selection**: Bank browser with category filtering, custom request text entry, drag-to-reorder, limit enforcement with warnings
4. **Definitions** (optional): 25+ standard legal definitions + custom definitions
5. **Preview**: Formatted document preview
6. **Generate & Download**: PDF or DOCX output

#### AI Suggestions

`POST /api/discovery/suggest` — Given claim types + party role + tool type, returns suggested request categories and specific items from the bank.

#### Claim-to-Discovery Mapping

19 claim types map to relevant SROG/RFPD/RFA categories via `claim_mapping.py`. Ensures attorneys get claim-specific discovery suggestions.

#### Limit Enforcement & Declaration of Necessity

- SROGs: 35 without CCP §2030.050(b) declaration (UI warns, doesn't block)
- RFAs: 35 fact/mixed without CCP §2033.050 declaration (law/opinion exempt)
- RFPDs: No statutory limit
- FROGs: Section-based (no per-section limit)

When SROGs exceed 35 or fact RFAs exceed 35, the backend automatically appends a **Declaration of Necessity** page to the generated DOCX. The declaration includes:
- CCP section citation (§2030.050 for SROGs, §2033.050 for RFAs)
- Attorney attestation that each request is warranted
- Request count and type identification
- Penalty of perjury signature block

### Knowledge Sources

Request banks are curated legal content (not from the RAG knowledge base). The AI suggestion endpoint uses claim type mappings to recommend relevant items.

### Key Files

- Models: `src/employee_help/discovery/models.py`, `case_info.py`, `definitions.py`
- DOCX builder: `src/employee_help/discovery/generator/docx_builder.py`
- PDF filler: `src/employee_help/discovery/generator/pdf_filler.py`
- POS builder: `src/employee_help/discovery/generator/pos_builder.py`
- Pleading template: `src/employee_help/discovery/generator/pleading_template.py`
- Request banks: `src/employee_help/discovery/banks/srogs.py`, `rfpds.py`, `rfas.py`, `frogs_general.py`, `frogs_employment.py`
- Claim mapping: `src/employee_help/discovery/claim_mapping.py`
- API routes: `src/employee_help/api/discovery_routes.py`
- Templates: `src/employee_help/discovery/generator/templates/pleading_paper.docx`, `pos_template.docx`
- Frontend wizards: `frontend/components/discovery/`

### Test Suite

| Test File | What It Covers |
|-----------|----------------|
| `test_discovery_docx.py` | DOCX pleading paper generation (SROGs/RFPDs/RFAs) |
| `test_discovery_pdf.py` | PDF form filling (DISC-001/002) |
| `test_discovery_pos.py` | Proof of Service generation |
| `test_discovery_limits.py` | CCP request limit tracking |
| `test_discovery_suggestions.py` | Claim-to-discovery mapping |
| `test_discovery_api.py` | API endpoints |
| E2E: `discovery-disc001.spec.ts` | 7 tests | Full wizard flow, PDF form field validation, auto-selected sections |
| E2E: `discovery-disc002.spec.ts` | 4 tests | Employment interrogatories, entity checkbox, PDF generation |
| E2E: `discovery-srogs.spec.ts` | 7 tests | 35-limit counter, select/deselect, custom requests, DOCX validation |
| E2E: `discovery-rfpds.spec.ts` | 5 tests | 7-step wizard, production instructions, DOCX validation |
| E2E: `discovery-rfas.spec.ts` | 5 tests | Fact limit, type badges, fact/genuineness radio, DOCX validation |
| E2E: `discovery-cross-tool.spec.ts` | 4 tests | sessionStorage persistence, case info/claims/party role across tools |
| E2E: `discovery-limits.spec.ts` | 4 tests | Declaration of Necessity warnings, CCP section citations |
| E2E: `discovery-mobile.spec.ts` | 6 tests | 375x812 viewport, 44px touch targets, step counter |
| E2E: `discovery-index.spec.ts` | 5 tests | 5 tool cards, format badges, breadcrumb, legal disclaimer |
| **E2E Total** | **49 tests** | **Full coverage of all 5 discovery workflows + cross-tool + mobile** |

---

## 5. Web Application

### What It Does

Full-stack web interface with a chat-based Q&A experience, topic browsing, assessment tools, and discovery document generation.

### User

Both — mode toggle switches between consumer and attorney experiences.

### Use Case

Primary user-facing interface. Consumers get accessible rights guidance; attorneys get statutory research assistance and document generation.

### Architecture

- **Backend**: FastAPI at `src/employee_help/api/` with SSE streaming
- **Frontend**: Next.js 16 (App Router) + Tailwind CSS + TypeScript at `frontend/`
- **Proxy**: Next.js rewrites `/api/*` to FastAPI `:8000`
- **State**: React Context (Mode, Consent, Discovery) + localStorage/sessionStorage
- **Analytics**: Plausible (privacy-friendly, no cookies)

### Features

#### Chat Interface (3-Zone Layout)

- **Zone 1 (Header)**: Mode toggle, new chat, tools link
- **Zone 2 (Scrollable)**: Turn progress, conversation threads, scroll-to-bottom FAB
- **Zone 3 (Fixed Input)**: Auto-growing textarea, stop button during streaming

**Streaming UX**: Typing dots animation → blinking cursor → token-by-token rendering → memoized markdown split (prevents re-render of completed paragraphs). 45s timeout resets on each SSE event. Stop button preserves partial response.

**Idle State**: Centered hero with topic links, claim type links, and tool quick-access cards.

#### Multi-Turn Conversation

- Session-based (client-generated UUID)
- Server-side turn enforcement (consumer: 3, attorney: 5)
- History sent with each request for context continuity
- Short follow-up expansion for better retrieval
- Turn progress indicator
- Conversation-ended banner with new chat CTA

#### Mode Switching

- Consumer ↔ Attorney toggle (persisted to localStorage)
- Mode-specific consent modal ("I understand this is/is not legal advice")
- Disables during streaming
- Drives: LLM selection, content filtering, response format, turn limit, prompt tone

#### Topic Pages (11 SSG pages)

Statically generated at build time for SEO. Topics: wages, discrimination, retaliation, leave, safety, workers comp, unemployment, contracts, public sector, unfair practices, complaint process.

**Each topic page includes**: Overview, primary agencies/codes, FAQs (with FAQPage schema.org markup), related tools, related topics, related claims, CTA to chat.

#### Source Display & Citations

- Sources list with chunk metadata (citation, category, heading, relevance score)
- Links to source URLs
- Citation confidence badges (attorney mode): verified (green) / unverified (yellow) / suspicious (red)
- Feedback buttons (thumbs up/down) on latest turn

#### Accessibility & Mobile

- 44px touch targets throughout
- `env(safe-area-inset-bottom)` for iOS notches
- `h-dvh` viewport locking with fallback
- Semantic HTML (headings, nav, section, article)
- Responsive Tailwind classes
- Mobile discovery wizard adaptation

### API Endpoints

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/api/health` | GET | Health check | — |
| `/api/ask` | POST | RAG chat (SSE stream) | 5/min, 500/day |
| `/api/deadlines` | POST | Deadline calculator | 20/min |
| `/api/agency-routing` | POST | Agency routing | 20/min |
| `/api/unpaid-wages` | POST | Wage calculator | 20/min |
| `/api/incident-guide` | POST | Incident docs | 20/min |
| `/api/intake-questions` | GET | Questionnaire schema | 20/min |
| `/api/intake` | POST | Evaluate intake | 20/min |
| `/api/intake-summary` | POST | Rights summary (SSE) | 5/min, 500/day |
| `/api/feedback` | POST | Thumbs up/down | 10/min |
| `/api/discovery/suggest` | POST | AI suggestions | 20/min |
| `/api/discovery/banks/{tool}` | GET | Request bank | 20/min |
| `/api/discovery/definitions` | GET | Legal definitions | 20/min |
| `/api/discovery/generate` | POST | Document generation (PDF/DOCX) | 20/min |
| `/api/discovery/generate-pos` | POST | Proof of Service (DOCX) | 20/min |

### Security

- CORS middleware (configurable origins)
- Per-IP rate limiting with sliding window + daily budget for LLM endpoints
- Prompt injection detection (regex-based pattern flagging)
- HTML/control character sanitization
- Safe filename generation for downloads
- No exposed API keys in frontend

### Key Files

- FastAPI app: `src/employee_help/api/main.py`
- Routes: `src/employee_help/api/routes.py`
- Discovery routes: `src/employee_help/api/discovery_routes.py`
- Schemas: `src/employee_help/api/schemas.py`
- Dependencies: `src/employee_help/api/deps.py`
- Sanitization: `src/employee_help/api/sanitize.py`
- Frontend app: `frontend/app/` (15 pages)
- Components: `frontend/components/` (29 TSX files)
- Hooks: `frontend/lib/use-conversation.ts`
- API clients: `frontend/lib/api.ts`, `frontend/lib/discovery-api.ts`
- Topics data: `frontend/lib/topics.ts`
- Claims data: `frontend/lib/claims.ts`
- Calculator libs: `frontend/lib/calculators/`

### Test Suite

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_api.py` | ~23 | SSE streaming, error handling, mode switching |
| `test_feedback_api.py` | ~24 | Query logging, citation audit, feedback |
| `test_feedback_store.py` | — | Feedback storage operations |
| `test_deadlines_api.py` | — | Deadline endpoint validation |
| `test_unpaid_wages_api.py` | — | Wage endpoint validation |
| `test_routing_api.py` | — | Agency routing endpoint |
| `test_incident_docs_api.py` | — | Incident guide endpoint |
| `test_intake_api.py` | — | Intake questionnaire endpoint |
| `test_intake_summary_api.py` | ~7 | SSE streaming, rate limiting |
| `test_discovery_api.py` | — | Discovery endpoints |
| `test_sanitize.py` | — | Input sanitization, injection detection |
| `test_sentry.py` | — | Error tracking integration |
| E2E (Playwright): 9 spec files | 49 | Full wizard flows, PDF/DOCX validation, mobile, cross-tool |

---

## 6. Analytics, Feedback & Quality Assurance

### What It Does

Tracks query volume, user feedback, citation accuracy, and session behavior. Provides CLI dashboards, automated evaluation pipelines, and cross-source validation reports.

### User

Internal (developer/operator).

### Use Case

Monitor product quality, identify areas for improvement, validate knowledge base integrity, and measure RAG answer quality over time.

### Features

#### Query Logging

Every `/api/ask` and `/api/intake-summary` request logs:
- `query_id` (UUID), `query_hash` (SHA-256), mode, model
- Token counts (input/output), cost estimate, duration
- Source count, error (if any), session_id

#### User Feedback

- Thumbs up (+1) / thumbs down (-1) per query
- Frontend: FeedbackButtons component, 44px touch targets
- API: `POST /api/feedback`
- Analytics: approval rate, feedback rate, daily trends

#### Citation Audit (Attorney Mode)

Per-citation logging:
- Citation text, type (case/statute)
- Verification status (verified/unverified/suspicious)
- Confidence level, detail reasoning
- Model used, session ID

CLI command: `employee-help citation-audit` with filters (--days, --session, --confidence, --csv).

#### Session Tracking

Multi-turn conversation sessions logged:
- Session ID, mode, turn count, created_at, last_active_at
- Aggregates: total sessions, avg turns, per-mode breakdown

#### Automated Evaluation

**Retrieval evaluation** (`evaluate-retrieval` CLI):
- Precision@5, Recall@5, MRR, Citation Hit@1
- Runs against YAML datasets (consumer, attorney, adversarial questions)
- Outputs JSON + Markdown report

**Answer evaluation** (`evaluate-answers` CLI):
- Disclaimer rate, reading level, citation completeness, cost
- Adversarial behavior checking (out-of-scope, citation-not-found, clarification)
- 60 questions, 96.7% disclaimer, 100% adversarial pass, 73% citation completeness

#### Cross-Source Validation

`cross-validate` CLI command:
- 7 check types across all sources
- Citation sampling (30 samples), content hash dedup detection
- Empty chunk detection, token boundary checks
- Generates JSON + Markdown reports
- Current: 32/33 checks pass (1 known CalHR token bounds issue)

#### Evaluation Datasets

| File | Questions | Purpose |
|------|-----------|---------|
| `consumer_questions.yaml` | 15 | Basic consumer scenarios |
| `attorney_questions.yaml` | 12 | Attorney Q&A pairs |
| `adversarial_questions.yaml` | 8 | Edge cases, out-of-scope |
| `consumer_conversations.yaml` | — | Multi-turn consumer |
| `attorney_conversations.yaml` | — | Multi-turn attorney |
| `consumer_validation.yaml` | — | Comprehensive validation |
| `attorney_validation.yaml` | — | Attorney validation |
| `attorney_questions_comprehensive.yaml` | — | Large comprehensive set |

### Key Files

- Feedback models: `src/employee_help/feedback/models.py`
- Feedback store: `src/employee_help/feedback/store.py`
- Retrieval metrics: `src/employee_help/evaluation/retrieval_metrics.py`
- Answer metrics: `src/employee_help/evaluation/answer_metrics.py`
- Validation report: `src/employee_help/validation_report.py`
- Eval datasets: `tests/evaluation/*.yaml`

### Test Suite

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_feedback_api.py` | ~24 | Query logging, feedback, citation audit |
| `test_feedback_store.py` | — | Storage operations, analytics queries |
| `test_evaluation_metrics.py` | — | Metric calculations |
| `test_cross_source.py` | — | Duplicate detection |
| `test_cross_source_validation.py` | — | Full validation reports |
| `test_validation.py` | — | Validation module |
| `test_ingestion_spot_check.py` | — | Live database spot checks |
| Evaluation: `test_retrieval_quality.py` | — | Aggregate retrieval metrics |
| Evaluation: `test_citation_integrity.py` | — | No hallucinated citations |

---

## 7. CLI Tooling

### What It Does

`employee-help` CLI provides 16 commands for data acquisition, search, generation, quality assurance, and analytics — covering the full lifecycle from ingestion to evaluation.

### User

Developer/operator.

### Commands

| Command | Category | Purpose |
|---------|----------|---------|
| `scrape` | Ingestion | Run pipeline for a source (statutory/crawler/caselaw) |
| `refresh` | Ingestion | Re-run pipeline, skip unchanged content |
| `pubinfo-download` | Ingestion | Download PUBINFO ZIP from leginfo |
| `ingest-caselaw` | Ingestion | Download case law from CourtListener |
| `status` | Monitoring | Display latest crawl run status |
| `embed` | RAG | Generate vector embeddings |
| `embed-status` | RAG | Show embedding coverage stats |
| `search` | RAG | Hybrid retrieval search |
| `ask` | RAG | RAG-generated answer from Claude |
| `validate` | QA | Phase 1G validation tests |
| `cross-validate` | QA | Cross-source validation (7 checks) |
| `evaluate-retrieval` | QA | Retrieval quality metrics |
| `evaluate-answers` | QA | Answer quality metrics |
| `feedback` | Analytics | Query analytics dashboard |
| `citation-audit` | Analytics | Citation verification report |
| `spot-check-caselaw` | QA | Random sampling quality review |

### Key File

- `src/employee_help/cli.py`

---

## 8. Cross-Product Integration Map

```
                    ┌─────────────────────────────────────┐
                    │     Knowledge Base (21 Sources)      │
                    │  Statutory │ Agency │ Case Law │ PDF │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │        RAG Pipeline (Hybrid)         │
                    │  Embed → Search → Retrieve → Score   │
                    └──────────────────┬──────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
     ┌────────▼────────┐    ┌─────────▼─────────┐    ┌────────▼────────┐
     │   Chat (Both)    │    │ Intake Summary    │    │  Citation Audit │
     │ Consumer/Attorney│    │   (Consumer)      │    │   (Attorney)    │
     └────────┬────────┘    └─────────┬─────────┘    └─────────────────┘
              │                        │
              │            ┌───────────┴───────────┐
              │            │  Guided Intake (Hub)   │
              │            │   8 branching Qs       │
              │            └───────────┬───────────┘
              │                        │ recommends
              │         ┌──────────────┼──────────────┐
              │    ┌────▼─────┐  ┌─────▼──────┐  ┌───▼────────┐
              │    │ Deadline │  │ Unpaid     │  │ Incident   │
              │    │ Calc     │  │ Wages Calc │  │ Docs Guide │
              │    └──────────┘  └────────────┘  └────────────┘
              │
              │    ┌─────────────────────────────────────┐
              │    │       Agency Routing Guide           │
              │    └─────────────────────────────────────┘
              │
     ┌────────▼────────────────────────────────────────────┐
     │              Discovery Tools (Attorney)              │
     │  DISC-001 │ DISC-002 │ SROGs │ RFPDs │ RFAs │ POS  │
     └─────────────────────────────────────────────────────┘
```

### Integration Points

| From | To | Integration |
|------|----|-------------|
| Guided Intake | All Assessment Tools | Pre-filled parameters (claim_type, issue_type, employment_status) |
| Guided Intake | RAG Pipeline | `build_intake_query()` → streaming rights summary |
| Topic Pages | Chat | "Ask about this topic" CTA |
| Topic Pages | Assessment Tools | Related tools section |
| Chat (Attorney) | Citation Verifier | Post-generation case + statute verification |
| Citation Verifier | CourtListener API | Case law lookup |
| Citation Verifier | Local DB | Statute lookup (is_active, recency) |
| Discovery Suggest | Request Banks | Claim-to-discovery mapping |
| Pipeline (Caselaw) | Citation Extractor | Eyecite extraction → CitationLink table |
| Pipeline (Caselaw) | Storage | `resolve_citation_targets()` bidirectional linking |
| Feedback | Analytics | Query logging → daily stats, approval rate |
| All LLM Endpoints | Rate Limiter | 5/min per IP + 500/day budget |

---

## 9. Test Suite Summary

### Overall Numbers

- **Total passing tests**: ~1,535
- **Deselected (slow/live/llm/eval markers)**: ~74
- **Total test files**: ~72 Python + 9 Playwright E2E specs
- **Evaluation datasets**: 8 YAML files

### Pytest Markers

| Marker | Purpose | Default Behavior |
|--------|---------|------------------|
| `integration` | Live external services | Deselected |
| `live` | Live government websites | Deselected |
| `slow` | ML model loading (~60s) | Deselected |
| `llm` | Live Claude API calls | Deselected |
| `evaluation` | RAG evaluation suites | Deselected |
| `validation` | Live API validation | Deselected |
| `spot_check` | Live ingested database | Deselected |

### Test Categories

| Category | Approx Tests | Scope |
|----------|-------------|-------|
| Unit (mocked, fast) | ~450 | Models, config, chunking, citation extraction, tools |
| Integration (DB, mock HTTP) | ~800 | Storage, crawling, pipeline, API endpoints |
| Slow (ML models) | ~50 | Real BGE embedding, LanceDB operations |
| Live (external services) | ~100 | Government websites, CourtListener, Claude API |
| Evaluation | ~50+ | Retrieval metrics, citation accuracy |
| E2E (Playwright) | 49 tests / 9 specs | Discovery wizard flows, PDF/DOCX content validation, mobile, cross-tool |

### Running Tests

```bash
# Fast unit + mock integration (~30-60s)
uv run pytest

# Include slow ML tests
uv run pytest -m slow

# Include live external service tests
uv run pytest -m live

# Include LLM evaluation tests (requires ANTHROPIC_API_KEY)
uv run pytest -m "llm or evaluation"

# Spot check against live database
uv run pytest -m spot_check

# Frontend E2E (auto-starts FastAPI + Next.js)
cd frontend && npm run test

# Everything
uv run pytest -m ""
```

---

## Grand Totals

| Metric | Value |
|--------|-------|
| Knowledge sources | 21 |
| Documents ingested | ~20,871 |
| Chunks (all active) | ~24,106 |
| Content categories | 12 |
| API endpoints | 15 |
| CLI commands | 16 |
| Assessment tools | 5 |
| Discovery document types | 6 |
| Request bank items | 177 role-aware (SROGs + RFPDs + RFAs) |
| Topic pages (SSG) | 11 |
| Employment claim types | 19 |
| Test files | ~81 (72 Python + 9 E2E) |
| Passing tests | ~1,535 |
| Evaluation questions | 60+ |
