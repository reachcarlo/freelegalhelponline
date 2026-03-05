# Employee Help -- Knowledge Source Inventory

> Last updated: 2026-03-03
> Total sources configured: 21 | Total ingested: ~10 | Total chunks: ~24,106

This document catalogs every knowledge source in the Employee Help platform: what it is, how it's used, how it's scored, what authority it carries, whether it's verified, and how (or whether) it can be kept evergreen.

---

## Table of Contents

- [Authority Hierarchy](#authority-hierarchy)
- [Retrieval Mode Summary](#retrieval-mode-summary)
- [Source Inventory](#source-inventory)
  - [Tier 1: Primary Law](#tier-1-primary-law)
    - [1. California Statutory Codes (PUBINFO)](#1-california-statutory-codes-pubinfo)
    - [2. CourtListener Case Law](#2-courtlistener-case-law)
  - [Tier 2: Binding Regulations & Quasi-Authoritative](#tier-2-binding-regulations--quasi-authoritative)
    - [3. CCR Title 2 -- FEHA Regulations](#3-ccr-title-2--feha-regulations)
    - [4. CCR Title 8 -- Industrial Relations](#4-ccr-title-8--industrial-relations)
    - [5. CACI Jury Instructions](#5-caci-jury-instructions)
  - [Tier 3: Persuasive Administrative Authority](#tier-3-persuasive-administrative-authority)
    - [6. DLSE Opinion Letters](#6-dlse-opinion-letters)
    - [7. DLSE Enforcement Manual](#7-dlse-enforcement-manual)
    - [8. EEOC Federal Guidance](#8-eeoc-federal-guidance)
  - [Tier 4: Agency Guidance & Educational](#tier-4-agency-guidance--educational)
    - [9. DIR/DLSE (Dept. of Industrial Relations)](#9-dirdlse-dept-of-industrial-relations)
    - [10. EDD (Employment Development Dept.)](#10-edd-employment-development-dept)
    - [11. CalHR (Dept. of Human Resources)](#11-calhr-dept-of-human-resources)
    - [12. CRD (Civil Rights Dept.)](#12-crd-civil-rights-dept)
    - [13. Legal Aid at Work](#13-legal-aid-at-work)
- [Ingestion & Freshness Pipeline](#ingestion--freshness-pipeline)
- [Gaps & Recommendations](#gaps--recommendations)

---

## Authority Hierarchy

The platform encodes a legal authority hierarchy through retrieval scoring boosts (applied in attorney mode only). Consumer mode receives no boosts -- raw hybrid search scores determine ranking.

| Tier | Content Category | Attorney Boost | Legal Weight |
|------|-----------------|---------------|--------------|
| 1 | `statutory_code` | 1.2x | Enacted law. Binding on all courts and agencies. |
| 1 | `case_law` | 1.25x | Published appellate opinions. Binding judicial precedent. |
| 2 | `regulation` | 1.2x | CCR provisions. Force and effect of law via APA rulemaking. |
| 2 | `jury_instruction` | 1.3x | Judicial Council CACI. Quasi-authoritative; affirmative burden to deviate. |
| 3 | `opinion_letter` | 1.15x | DLSE interpretations. Persuasive; binding in DLSE proceedings only. |
| 3 | `enforcement_manual` | 1.1x | DLSE policy manual. Persuasive; often cited by courts. |
| 3 | `federal_guidance` | 1.1x | EEOC guidance. Skidmore deference (persuasive, not binding). |
| 4 | `agency_guidance` | 1.0x | State agency web content. Informative, not legally binding. |
| 4 | `fact_sheet` / `faq` | 1.0x | Plain-language summaries. No legal authority. |
| 4 | `legal_aid_resource` | 1.0x | Nonprofit educational material. No legal authority. |

**Additional citation-specific boosts (attorney mode):**
- Substring citation match: 1.5x
- Exact section match bonus: additional 2.0x
- Maximum combined citation boost: up to 3.0x (before category boost)

---

## Retrieval Mode Summary

| Category | Consumer Mode | Attorney Mode |
|----------|:------------:|:-------------:|
| `agency_guidance` | Included | Included (1.0x) |
| `fact_sheet` | Included | Included (1.0x) |
| `faq` | Included | Included (1.0x) |
| `legal_aid_resource` | Included | Included (1.0x) |
| `opinion_letter` | Included | Included (1.15x) |
| `enforcement_manual` | Included | Included (1.1x) |
| `federal_guidance` | Included | Included (1.1x) |
| `regulation` | Included | Included (1.2x) |
| `statutory_code` | **Excluded** | Included (1.2x) |
| `case_law` | **Excluded** | Included (1.25x) |
| `jury_instruction` | **Excluded** | Included (1.3x) |

Consumer mode filters to 8 categories focused on plain-language, actionable guidance. Attorney mode includes all 11 categories with authority-weighted boosts.

---

## Source Inventory

### Tier 1: Primary Law

---

#### 1. California Statutory Codes (PUBINFO)

**9 source configs covering 9 California codes:**

| Config File | Code | Slug | Abbreviation | Target Divisions | Documents | Chunks |
|-------------|------|------|-------------|-----------------|-----------|--------|
| `labor_code.yaml` | Labor Code | `labor_code` | LAB | All (7 divisions) | 2,631 | 2,733 |
| `gov_code_feha.yaml` | Gov Code -- FEHA | `gov_code_feha` | GOV | Div 3 | 4,649 | 4,718 |
| `gov_code_whistleblower.yaml` | Gov Code -- Whistleblower | `gov_code_whistleblower` | GOV | Divs 1-2 | 7,772 | 7,980 |
| `unemp_ins_code.yaml` | Unemployment Insurance Code | `unemp_ins_code` | UIC | Div 1 | 838 | 850 |
| `bus_prof_code.yaml` | Bus. & Prof. Code | `bus_prof_code` | BPC | Div 7 | 475 | 492 |
| `ccp.yaml` | Code of Civil Procedure | `ccp` | CCP | All | 3,411 | 3,447 |
| `health_safety_code.yaml` | Health & Safety Code | `health_safety_code` | HSC | Div 5 | P2 | P2 |
| `education_code.yaml` | Education Code | `education_code` | EDC | Div 4 | P2 | P2 |
| `civil_code.yaml` | Civil Code | `civil_code` | CIV | Divs 1, 3 | P2 | P2 |

> **P2** = Phase 2 expansion. Config exists and is enabled but may not yet be ingested/embedded.

**What it is:** The actual text of California statutory law as enacted by the Legislature and signed by the Governor. This is the controlling substantive law for all California employment rights claims.

**What we pull in:** Every active section of each targeted code/division. For Labor Code, that means all 7 divisions (2,631 sections). Section text includes the full statutory language, subdivision structure, amendment history, and effective dates.

**Data source:** PUBINFO database from `https://downloads.leginfo.legislature.ca.gov/`. This is an official bulk data export of the California legislative information system. The archive (`pubinfo_2025.zip`, 677.5 MB) contains tab-delimited `.dat` files with LOB sidecar files (185,713 `.lob` files, 162,169 total sections). A web scraper (`StatutoryExtractor` via httpx + BeautifulSoup against leginfo.legislature.ca.gov) exists as a fallback.

**Pipeline:**
1. `PubinfoLoader` downloads/caches the full archive
2. Parses `LAW_SECTION_TBL.dat` + resolves `.lob` HTML sidecar files
3. Filters by code abbreviation, target divisions, and `active_flg == "Y"`
4. Converts HTML to plain text, builds citations (e.g., "Cal. Lab. Code § 1102.5"), hierarchy paths
5. Chunks via `section_boundary` strategy (one section = one chunk if ≤2,000 tokens; splits at subdivision boundaries otherwise)
6. Upserts documents with content_hash dedup; soft-deletes repealed sections via `is_active` flag

**Scoring:** 1.2x boost in attorney mode. Up to 3.0x additional for exact citation matches. Excluded from consumer mode entirely (consumers get agency-language explanations instead of raw statute text).

**Validation:**
- Cross-source validation checks: all chunks have citations, citations match `^Cal\.\s+.+\s+§\s+\d+` format, no empty chunks, token bounds within 1-10,000
- `StatuteCitationVerifier` verifies statute citations in LLM answers against the local SQLite DB: checks existence, active status, and staleness (30-day amendment threshold)
- 30/30 sampled citations passed format validation (latest run)

**Cited in application:** Yes. Attorney mode cites specific section numbers (e.g., "Cal. Lab. Code § 1102.5"). Consumer mode references statutes only if the user explicitly asks for section numbers; otherwise the system prompt directs the LLM to describe rights without citing statute numbers.

**Verified:** Yes. `StatuteCitationVerifier` checks every statute citation the LLM produces against the local knowledge base. Results are: `VERIFIED` (found, active, fresh), `NOT_FOUND`, `REPEALED` (soft-deleted), or `AMENDED` (stale). Verification results are sent to the frontend in the `done` SSE event and displayed via `<CitationBadges>`.

**Authority type:** Primary law (binding). The highest tier of authority in the system.

**Source update cadence:**
- Most new laws take effect **January 1** annually. The Governor signs bills August-October.
- Urgency statutes can take effect immediately upon signing (rare).
- The PUBINFO `law_section_tbl` is updated in the weekly full archive; daily deltas contain only bill data.
- In 2025, Governor Newsom signed 794 bills into law.

**Our maintenance pipeline:**
- CLI: `employee-help pubinfo-download --year 2025 [--force]` → `employee-help scrape --source labor_code` → `employee-help embed --source labor_code`
- Change detection: `upsert_document()` compares content_hash; `refresh` CLI reports changes
- Soft-delete: `deactivate_missing_sections()` marks repealed sections `is_active = false`
- **Current gap:** No automated cron job. Weekly manual re-download recommended. The requirements doc flags automated refresh as P0 for Phase 5B.

**Recommendation:** Weekly full archive re-download (`--force`) is the minimum cadence. Should be automated via cron or CI pipeline. Critical refresh window: late December through January (annual code updates).

---

#### 2. CourtListener Case Law

| Config | `courtlistener.yaml` |
|--------|---------------------|
| Slug | `courtlistener` |
| Content Category | `case_law` |
| Courts | California Supreme Court (`cal`), Court of Appeal (`calctapp`) |
| Filed After | 1990-01-01 |
| Max Opinions | 5,000 |

**What it is:** Published California appellate court opinions interpreting and applying employment law statutes. This is binding judicial precedent -- co-equal with statutory law as primary authority.

**What we pull in:** Opinions from CourtListener (operated by Free Law Project, a nonprofit) filtered by 10 employment-specific search queries targeting FEHA, Labor Code retaliation, PAGA, wrongful termination, wage and hour, and employment discrimination. Each opinion is further filtered for employment relevance by checking for citations to key FEHA sections (§§ 12940, 12945, etc.) and Labor Code sections (§§ 98, 98.6, 200, 226, 510, 1102.5, 2699, etc.).

**Pipeline:**
1. `CourtListenerClient` authenticates via API token, rate-limited (5,000 req/hr)
2. `OpinionLoader` executes search queries, downloads opinion text (prefers `html_with_citations` format)
3. `citation_extractor` (eyecite wrapper) extracts all case and statute citations from opinion text
4. Employment relevance filter: must cite key employment statutes or match search terms
5. `chunk_case_law()` splits long opinions at paragraph boundaries; prepends citation header to continuation chunks
6. Creates bidirectional `CitationLink` objects (case → statute, statute → case)
7. `resolve_citation_targets()` maps citation links to target chunks in the local DB

**Scoring:** 1.25x boost in attorney mode. Excluded from consumer mode.

**Validation:**
- `CaseCitationVerifier` looks up each case citation the LLM produces via the CourtListener API
- Checks: exists in CourtListener, is California jurisdiction, filing year matches citation year
- Verification statuses: `VERIFIED`, `NOT_FOUND`, `WRONG_JURISDICTION`, `DATE_MISMATCH`, `AMBIGUOUS`, `ERROR`
- Confidence scoring: VERIFIED → green, NOT_FOUND/AMBIGUOUS → yellow, WRONG_JURISDICTION/DATE_MISMATCH → red

**Cited in application:** Yes, in attorney mode only. Case citations appear in the LLM's analysis with full reporter citations (e.g., "Smith v. Jones (1995) 45 Cal.3d 123").

**Verified:** Yes. `CaseCitationVerifier` performs live API lookups against CourtListener for every case citation. Results displayed in `<CitationBadges>` on the frontend.

**Authority type:** Primary law (binding judicial precedent). Published Supreme Court opinions bind statewide. Court of Appeal opinions bind within their district and persuade elsewhere. Unpublished opinions are not citable under Cal. Rules of Court, rule 8.1115.

**Source update cadence:**
- CourtListener scrapes new opinions **daily** from ~200 courts
- California appellate courts update case information hourly during business days
- Coverage: claimed >99% of all precedential U.S. case law

**Our maintenance pipeline:**
- CLI: `employee-help ingest-caselaw` → `employee-help embed --source courtlistener`
- API token required: `COURTLISTENER_API_TOKEN` env var
- Retry with backoff on 5xx errors; handles 429 rate limits via Retry-After
- **Current gap:** No automated periodic re-ingestion. Monthly refresh recommended to capture new opinions.

**Recommendation:** Monthly re-ingestion to capture new opinions. High-profile employment law decisions (e.g., new Supreme Court rulings on PAGA, FEHA burden-shifting) should trigger ad-hoc refreshes.

---

### Tier 2: Binding Regulations & Quasi-Authoritative

---

#### 3. CCR Title 2 -- FEHA Regulations

| Config | `ccr_title2_feha.yaml` |
|--------|----------------------|
| Slug | `ccr_title2_feha` |
| Content Category | `regulation` |
| Data Source | Cornell LII (`law.cornell.edu`) |
| Scope | Title 2, Div 4.1, Ch 5, Subch 2 (~80 sections, 11 articles) |

**What it is:** The implementing regulations for FEHA, promulgated by the Civil Rights Department (formerly DFEH) through the APA rulemaking process. These have the **force and effect of law** -- courts must apply them and employers must comply. Topics include: reasonable accommodation, interactive process, harassment training requirements, pregnancy disability leave, CFRA implementation.

**What we pull in:** ~80 regulation sections scraped from Cornell Legal Information Institute. Each section includes the regulation text and source notes.

**Pipeline:**
1. `ccr_web` method: hardcoded manifest of section numbers
2. Fetches each section from Cornell LII via httpx
3. Parses with BeautifulSoup (extracts `div.statereg-text` and `div.statereg-notes`)
4. Caches raw HTML locally in `data/ccr/`
5. Converts to `StatuteSection` objects, chunked via `section_boundary`

**Scoring:** 1.2x boost in attorney mode. Included in consumer mode (no boost).

**Validation:** Covered by cross-source validation checks. No specialized regulation verifier exists.

**Cited in application:** Yes, as "2 CCR § [section]" in attorney mode.

**Verified:** Partially. No live verification against the official OAL CCR database. Content is verified only by cross-source validation at ingestion time.

**Authority type:** Binding administrative regulations. Force and effect of law.

**Source update cadence:**
- OAL updates the CCR **weekly**
- Employment-related regulatory changes are less frequent (major FEHA regulation updates every few years)
- Rulemaking process takes 6-12 months from proposed action to final adoption

**Our maintenance pipeline:**
- Sourced from Cornell LII (third-party mirror of official CCR)
- **Current gap:** Cornell LII may lag behind OAL's official updates. No automated refresh. Consider switching to official OAL source or Westlaw/Lexis for authoritative text.

**Recommendation:** Monthly re-scrape from Cornell LII. Consider migrating to the official OAL Westlaw CCR database for guaranteed freshness.

---

#### 4. CCR Title 8 -- Industrial Relations

| Config | `ccr_title_8.yaml` |
|--------|-------------------|
| Slug | `ccr_title_8` |
| Content Category | `regulation` |
| Data Source | Cornell LII |
| Scope | Title 8, Div 1 (workplace safety, wage/hour regulations) |

**What it is:** Cal/OSHA and wage/hour implementing regulations under Title 8. Covers workplace safety standards, IWC wage order enforcement provisions, and related industrial relations regulations.

**Pipeline:** Same as CCR Title 2 (`ccr_web`/`ccr_title_8` method via Cornell LII).

**Scoring, validation, authority, maintenance:** Same as CCR Title 2 above.

**Recommendation:** Same as CCR Title 2 -- monthly refresh, consider official OAL source.

---

#### 5. CACI Jury Instructions

| Config | `caci.yaml` |
|--------|------------|
| Slug | `caci` |
| Content Category | `jury_instruction` |
| Current Edition | 2026 (`data/caci/caci_2026.pdf`, 3,560 pages) |
| Coverage | 6 employment series: 2400-2499, 2500-2599, 2600-2699, 2700-2799, 2800-2899, 4600-4699 |
| Stats | 110 instructions → 325 documents → 353 chunks |

**What it is:** The official civil jury instructions approved by the Judicial Council of California under Cal. Rules of Court, rule 2.1050. CACI instructions define the **elements** that must be proved for each cause of action. A judge has an affirmative burden to justify deviating from CACI when an applicable instruction exists. For employment attorneys, CACI is indispensable -- it tells you exactly what you need to prove (or defend against) for wrongful termination, discrimination, harassment, retaliation, wage claims, and more.

**What we pull in:** All employment-related CACI instructions. Each instruction is split into up to 4 sections:
1. `instruction_text` -- The actual jury instruction (claim elements, burdens of proof)
2. `directions_for_use` -- Practical guidance for judges/attorneys on when and how to use the instruction
3. `sources_and_authority` -- Case law citations supporting each element
4. `secondary_sources` -- Treatise references (merged into sources_and_authority chunk)

**Pipeline:**
1. `CACILoader` parses the official Judicial Council PDF via pdfplumber
2. Detects instruction boundaries via regex (`^\d{4}[A-Z]?\.\s+`)
3. Splits into sections per instruction
4. Handles letter suffixes (2521A/B/C, 2522A/B/C), TOC pages, Verdict Form entries (VF-XXXX)
5. Each section gets a unique source_url with fragment: `#CACI-{number}-{section_key}`
6. Heading path: "CACI > Wrongful Termination > No. 2430 -- Title > Instruction Text"

**Scoring:** 1.3x boost in attorney mode (the highest category boost). Excluded from consumer mode.

**Validation:** Covered by cross-source validation. No specialized CACI verifier.

**Cited in application:** Yes, in attorney mode. Referenced as "CACI No. [number]" with instruction text and elements.

**Verified:** At source level only (we use the official Judicial Council PDF). No live verification.

**Authority type:** Quasi-authoritative. Not technically law, but approved by the Judicial Council and given strong deference by trial courts. The 1.3x boost (highest of any category) reflects this practical importance for attorneys.

**Source update cadence:**
- **Biannual**: main edition in November, supplement in May/July
- The Advisory Committee on Civil Jury Instructions reviews new case law and statutes continuously

**Our maintenance pipeline:**
- Manual PDF download from the Judicial Council website
- **Current gap:** Requires manual download of the new PDF twice yearly. No automated detection of new editions.

**Recommendation:** Set calendar reminders for November and May/July CACI releases. Download new PDF, replace `data/caci/caci_2026.pdf`, re-run ingestion. Consider automating the PDF download check.

---

### Tier 3: Persuasive Administrative Authority

---

#### 6. DLSE Opinion Letters

| Config | `dlse_opinions.yaml` |
|--------|---------------------|
| Slug | `dlse_opinions` |
| Content Category | `opinion_letter` |
| Scope | 1983-2019 archive of Labor Commissioner interpretive letters |
| Method | `dlse_opinions` (two-phase: scrape HTML index → download + parse PDFs) |

**What it is:** Interpretive guidance letters issued by the California Labor Commissioner in response to specific wage and hour questions. Not binding on courts, but persuasive -- courts frequently cite them. Binding in DLSE proceedings (wage claims before the Labor Commissioner). Not a safe harbor for employers.

**What we pull in:** Letters indexed at `dir.ca.gov/dlse/opinionletters-bysubject.htm`. Two-phase extraction: scrape HTML index for PDF URLs, dates, and subjects, then download and parse each PDF via pdfplumber. Statute citations are extracted from the letter text.

**Scoring:** 1.15x boost in attorney mode. Included in consumer mode (no boost).

**Cited in application:** Yes. Referenced as "DLSE Opinion Letter" in both modes.

**Verified:** At source level (official DIR website). No live verification of individual letter citations.

**Authority type:** Persuasive administrative guidance. Courts sometimes follow, sometimes disagree.

**Source update cadence:** The opinion letter program has been **largely dormant since ~2019**. This is essentially a **static, closed corpus**.

**Our maintenance pipeline:** One-time ingestion. No regular refresh needed since no new letters are being issued.

**Recommendation:** Annual check of the DIR index page to confirm no new letters have been published. Otherwise, this source is maintenance-free.

---

#### 7. DLSE Enforcement Manual

| Config | `dlse_manual.yaml` |
|--------|-------------------|
| Slug | `dlse_manual` |
| Content Category | `enforcement_manual` |
| Source | Single PDF: `dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf` (352 pages, ~53 chapters) |
| Method | `dlse_manual` |

**What it is:** The DLSE Enforcement Policies and Interpretations Manual (originally 2002, last revised May 2020). A comprehensive policy manual governing how DLSE staff investigate and adjudicate wage claims. Judges often cite it as persuasive authority. For attorneys, it reveals how the Labor Commissioner actually interprets and applies wage/hour statutes in practice.

**What we pull in:** The full manual. Parsed via pdfplumber, split into chapters at chapter boundaries. Each chapter becomes one `StatuteSection`. Heading path: "DLSE Manual > Chapter 2 -- WAGES".

**Scoring:** 1.1x boost in attorney mode. Included in consumer mode (no boost).

**Cited in application:** Yes. Referenced as "DLSE Enforcement Manual" in both modes.

**Verified:** At source level (official DIR PDF). No live verification.

**Authority type:** Persuasive agency interpretive guidance.

**Source update cadence:** **Infrequent** -- years between revisions. Last substantive update was May 2020 (COVID-related leave provisions).

**Our maintenance pipeline:** One-time ingestion. Semi-annual check of the PDF URL for updated versions.

**Recommendation:** Semi-annual check. The manual is stable enough that annual re-ingestion is sufficient.

---

#### 8. EEOC Federal Guidance

| Config | `eeoc.yaml` |
|--------|------------|
| Slug | `eeoc` |
| Content Category | `federal_guidance` |
| Base URL | `https://www.eeoc.gov` |
| Max Pages | 150 |
| Rate Limit | 3.0s |

**What it is:** Federal employment discrimination guidance from the U.S. Equal Employment Opportunity Commission. Covers Title VII, ADA, ADEA, GINA, and EPA. EEOC guidance receives **Skidmore deference** from courts (persuasive based on reasoning quality, not automatic). Supplements California FEHA coverage with federal frameworks that California courts sometimes adopt.

**What we pull in:** Formal guidance documents, policy interpretations, and discrimination type overview pages. Excludes: news/press releases, litigation tracking, federal sector content, filing procedures, Spanish-language pages, PDFs.

**Pipeline:** Standard agency crawler (Playwright). Seed URLs include guidance-by-subject index and individual discrimination type pages. Content extracted from `#main-content`. Heading-based chunking (200-1500 tokens).

**Scoring:** 1.1x boost in attorney mode. Included in consumer mode (no boost).

**Cited in application:** Yes. Referenced as EEOC guidance in both modes.

**Verified:** At source level only. No live verification against EEOC.

**Authority type:** Federal persuasive authority (Skidmore deference). Not binding on California state courts but frequently cited as persuasive, especially where FEHA and Title VII overlap.

**Source update cadence:**
- **Irregular and politically dependent.** Major guidance documents updated every few years.
- The current administration (2025-2026) has rescinded some prior guidance and issued new enforcement priorities (e.g., DEI scrutiny).
- Strategic Enforcement Plan covers multi-year periods (current: FY 2024-2028).

**Our maintenance pipeline:**
- Standard Playwright crawl with 150-page cap
- **Current status:** Config exists and is enabled. May not yet be ingested (appears as untracked file in git status).

**Recommendation:** Quarterly re-crawl to capture guidance changes, especially during administration transitions. Monitor EEOC newsroom for rescissions of existing guidance.

---

### Tier 4: Agency Guidance & Educational

---

#### 9. DIR/DLSE (Dept. of Industrial Relations)

| Config | `dir.yaml` |
|--------|-----------|
| Slug | `dir` |
| Content Category | `agency_guidance` (default) |
| Max Pages | 300 |
| Rate Limit | 2.0s |
| Stats | 270 documents, 1,757 chunks (30 errors / 10% error rate) |

**What it is:** DIR is the state agency that administers and enforces California labor laws. DLSE (Division of Labor Standards Enforcement) handles wage claims, retaliation complaints, and labor law enforcement. DIR web content includes FAQs, know-your-rights brochures, wage orders, filing procedures, and policy guidance.

**What we pull in:** DLSE pages (FAQs, wages/hours, retaliation, publications, know-your-rights), IWC wage orders, Public Works/prevailing wage content, PAGA content, English PDFs. Excludes: non-employment divisions (OSHA, workers' comp, apprenticeship), non-English content, interactive databases, administrative pages.

**Pipeline:** Playwright crawler → BeautifulSoup HTML extraction (`#main-content`) → boilerplate removal → heading-based chunking (200-1500 tokens, 100 overlap). Content category auto-classified: FAQ URLs → `faq`, fact-sheet URLs → `fact_sheet`, default → `agency_guidance`.

**Scoring:** No boost in either mode (1.0x). Included in both consumer and attorney modes.

**Cited in application:** Yes. Consumer mode references DIR naturally ("According to the Department of Industrial Relations..."). Attorney mode includes DIR content when relevant but prioritizes statutory and case law sources.

**Verified:** At source level (official .gov website). No live verification of individual claims made in DIR content.

**Authority type:** Administrative guidance. Not legally binding, but DIR is the enforcing agency -- their interpretations carry practical weight even though courts are not bound by them.

**Source update cadence:** Event-driven. New content when minimum wage changes, new laws take effect, or policy interpretations change. Practically: monthly to quarterly on active topics, some pages static for years.

**Our maintenance pipeline:**
- CLI: `employee-help scrape --source dir` → `employee-help embed --source dir`
- **Current gap:** No automated scheduling. 10% crawl error rate should be investigated.

**Recommendation:** Weekly re-crawl. Investigate and fix the 30 crawl errors. Critical refresh window: late December / early January (annual law changes, minimum wage updates).

---

#### 10. EDD (Employment Development Dept.)

| Config | `edd.yaml` |
|--------|-----------|
| Slug | `edd` |
| Content Category | `agency_guidance` (default) |
| Max Pages | 200 |
| Stats | 200 documents, 411 chunks (0% errors) |

**What it is:** EDD administers California's unemployment insurance (UI), state disability insurance (SDI), and paid family leave (PFL) programs. Their web content explains eligibility, filing procedures, benefit amounts, and employer obligations under these programs.

**What we pull in:** Unemployment insurance, disability insurance, paid family leave, and jobs/training pages. Excludes: employer/tax administration, physician pages, voluntary plans, newsroom, non-English content, subdomains (myedd, askedd, etc.).

**Pipeline:** Same as DIR (Playwright → BeautifulSoup → heading-based chunking). Content selector: `.main-primary`.

**Scoring:** No boost (1.0x). Included in both modes.

**Cited in application:** Yes. Referenced as EDD guidance in both modes.

**Authority type:** Administrative guidance. Authoritative for the programs EDD administers (UI, SDI, PFL), but not binding on courts for questions of statutory interpretation.

**Source update cadence:** Event-driven. Benefit rate changes typically January 1 annually. EDD is undergoing a major modernization (EDDNext). Some pages updated quarterly, others static for years.

**Our maintenance pipeline:**
- Standard crawl pipeline
- **Current gap:** No automated scheduling.

**Recommendation:** Weekly re-crawl. Monitor EDDNext for structural changes that could break crawl selectors.

---

#### 11. CalHR (Dept. of Human Resources)

| Config | `calhr.yaml` |
|--------|-------------|
| Slug | `calhr` |
| Content Category | `agency_guidance` (tagged `state_employees` metadata) |
| Max Pages | 300 |
| Stats | 300 documents, 1,365 chunks (0% errors) |
| Known Issue | 1 chunk at 37,820 tokens (policy-memos page) |

**What it is:** CalHR sets HR policies for California state government employees. Their content covers leave/benefits, salaries/compensation, labor relations, bargaining contracts, pay scales, and career services. **Narrower audience** than other sources -- only relevant to state employees.

**What we pull in:** State employee policies, HR professional resources, leave/benefits, salaries, labor relations, forms, statutory appeals, FAQ. Excludes: external sites (CalPERS, CalCareers), news/blog posts, organizational/administrative pages, WordPress system files.

**Pipeline:** Same as DIR/EDD (Playwright → BeautifulSoup → heading-based chunking). Content selector: `#et-main-area`.

**Scoring:** No boost (1.0x). Included in both modes.

**Authority type:** Administrative guidance. Binding on state agencies as the employer, but not on courts in employment disputes.

**Source update cadence:** Rolling, quarterly to semi-annual substantive changes. Correlates with bargaining contract updates and legislative changes affecting state employees.

**Our maintenance pipeline:**
- Standard crawl pipeline
- **Current gap:** No automated scheduling. Known oversized chunk (37,820 tokens) needs chunker fix.

**Recommendation:** Weekly re-crawl. Fix the oversized chunk by implementing max-chunk-size enforcement in the heading-based chunker.

---

#### 12. CRD (Civil Rights Dept.)

| Config | `crd.yaml` |
|--------|-----------|
| Slug | `crd` |
| Content Category | `agency_guidance` (default) |
| Max Pages | 100 |

**What it is:** CRD (formerly DFEH) enforces California's civil rights laws, primarily FEHA. Their web content covers employment discrimination, harassment, the complaint process, posters, the Fair Chance Act, and sexual harassment prevention training FAQs.

**What we pull in:** Employment section, complaint process, posters/resources, Fair Chance Act, SHPT FAQ. Excludes: housing, hate violence, whistleblower (separate from employment retaliation), regulatory filings, pay data reporting, non-employment fact sheets.

**Pipeline:** Same as DIR (Playwright → BeautifulSoup → heading-based chunking). Content selector: `#et-main-area`.

**Scoring:** No boost (1.0x). Included in both modes.

**Authority type:** Administrative guidance. CRD enforces FEHA, so their interpretations of FEHA carry practical weight.

**Source update cadence:** Event-driven. Correlates with FEHA regulatory changes and new law implementations.

**Recommendation:** Weekly re-crawl. CRD is smaller (100 pages) and crawls quickly.

---

#### 13. Legal Aid at Work

| Config | `legal_aid_at_work.yaml` |
|--------|------------------------|
| Slug | `legal_aid_at_work` |
| Content Category | `legal_aid_resource` |
| Max Pages | 150 |
| Rate Limit | 10.0s (polite crawl for nonprofit) |

**What it is:** A nonprofit legal services organization (100+ years old) that produces 180+ fact sheets explaining California employment rights in plain language. Written by employment lawyers. Fact sheets cover wages, discrimination, leave, disability, immigration, workplace injury.

**What we pull in:** Individual fact sheets only (not archive index pages, topic category navigation, guides, sample letters, or organizational pages). Excludes: non-English translations, donate/news/events pages, WordPress infrastructure.

**Pipeline:** Same as agency sources (Playwright → BeautifulSoup → heading-based chunking). Content selector: `main`. Higher rate limit (10.0s) out of respect for nonprofit infrastructure.

**Scoring:** No boost (1.0x). Included in consumer mode only at base relevance; included in attorney mode at 1.0x.

**Cited in application:** Yes. Referenced as Legal Aid at Work fact sheets in consumer mode (especially useful for plain-language explanations).

**Verified:** At source level (authored by employment attorneys at a reputable nonprofit). No live verification.

**Authority type:** Secondary/educational. No legal authority whatsoever -- cannot be cited in court. But among the most accessible and reliable plain-language explanations of California employment rights.

**Source update cadence:** No published schedule. Likely updated when major legislative changes affect covered topics (annually around January 1). Update frequency depends on organizational capacity.

**Our maintenance pipeline:**
- Standard crawl pipeline
- **Current status:** Config exists and is enabled. May not yet be ingested (appears as untracked in git status).

**Recommendation:** Monthly re-crawl. Particularly important to refresh after January 1 each year when new laws take effect and dollar amounts (minimum wage, penalty amounts) change.

---

## Ingestion & Freshness Pipeline

### Current Architecture

```
Source YAML Config
    │
    ▼
Pipeline.run()
    ├── _run_statutory()     ← PUBINFO / PDF / CCR / DLSE / Web fallback
    ├── _run_caselaw()       ← CourtListener API
    └── _run_crawler()       ← Playwright (agency websites)
            │
            ▼
    Extraction (source-specific)
            │
            ▼
    Chunking (heading_based or section_boundary)
            │
            ▼
    Storage (SQLite, content_hash dedup, soft-delete)
            │
            ▼
    Embedding (bge-base-en-v1.5 → LanceDB)
            │
            ▼
    FTS Index Rebuild (BM25)
```

### Change Detection Mechanisms

| Mechanism | Scope | How It Works |
|-----------|-------|-------------|
| `content_hash` | All sources | SHA-256 of chunk content. `upsert_document()` skips unchanged documents. |
| `is_active` flag | Statutory | `deactivate_missing_sections()` soft-deletes sections no longer in source data. |
| `is_new` flag | All sources | Pipeline checks before inserting chunks; prevents duplicate chunk creation. |
| Cross-source validation | All sources | 7 check types: content verification, citation format, token bounds, duplicates, empty chunks. |

### CLI Commands

| Command | Purpose |
|---------|---------|
| `employee-help pubinfo-download` | Download PUBINFO archive |
| `employee-help scrape --source [slug]` | Run extraction pipeline for a source |
| `employee-help embed --source [slug]` | Generate embeddings for a source |
| `employee-help embed-status` | Check embedding coverage |
| `employee-help refresh` | Re-run pipeline, report changes |
| `employee-help validate` | Run validation checks |
| `employee-help cross-validate` | Full cross-source validation report |
| `employee-help ingest-caselaw` | Run case law ingestion |
| `employee-help spot-check-caselaw` | Spot-check case law quality |

### Current Gaps

1. **No automated refresh pipeline.** All ingestion is manual via CLI. The requirements doc identifies automated content refresh as **P0 priority** for Phase 5B: "Without this, the knowledge base decays. California laws change every January 1. Stale content destroys trust."

2. **No staleness monitoring.** No dashboard or alert when sources haven't been refreshed within their recommended cadence.

3. **Three P2 statutory codes** (Health & Safety, Education, Civil) are configured but may not be ingested/embedded yet.

4. **Two new agency sources** (EEOC, Legal Aid at Work) are configured but appear as untracked in git -- likely not yet ingested.

5. **Cornell LII dependency** for CCR regulations. Third-party mirror may lag behind official OAL source.

6. **CalHR oversized chunk** (37,820 tokens) -- heading-based chunker doesn't enforce max-chunk-size split.

7. **DIR 10% crawl error rate** -- 30 of 300 URLs failed during last crawl.

---

## Gaps & Recommendations

### Recommended Refresh Schedule

| Source | Cadence | Trigger Window | Priority |
|--------|---------|---------------|----------|
| Statutory Codes (PUBINFO) | Weekly | Late Dec - Jan (annual code updates) | P0 |
| DIR, EDD, CalHR, CRD | Weekly | Late Dec - Jan; minimum wage changes | P0 |
| Case Law (CourtListener) | Monthly | After major appellate decisions | P1 |
| CCR Regulations | Monthly | After OAL weekly updates | P1 |
| EEOC Federal Guidance | Quarterly | Administration transitions; guidance rescissions | P2 |
| CACI Jury Instructions | Biannually | November edition; May/July supplement | P2 |
| Legal Aid at Work | Monthly | After Jan 1 annual law changes | P2 |
| DLSE Enforcement Manual | Semi-annually | Check for PDF revision | P3 |
| DLSE Opinion Letters | Annually | Confirm no new letters | P3 |

### Sources Not Yet Fully Operational

| Source | Config Exists | Ingested | Embedded | Blocker |
|--------|:------------:|:--------:|:--------:|---------|
| Health & Safety Code | Yes | Likely not | Likely not | P2 expansion; needs pipeline run |
| Education Code | Yes | Likely not | Likely not | P2 expansion; needs pipeline run |
| Civil Code | Yes | Likely not | Likely not | P2 expansion; needs pipeline run |
| EEOC | Yes | Likely not | Likely not | Untracked in git; needs first crawl |
| Legal Aid at Work | Yes | Likely not | Likely not | Untracked in git; needs first crawl |
| CCR Title 2 | Yes | Unknown | Unknown | Needs verification |
| CCR Title 8 | Yes | Unknown | Unknown | Needs verification |
| DLSE Opinion Letters | Yes | Unknown | Unknown | Needs verification |
| DLSE Enforcement Manual | Yes | Unknown | Unknown | Needs verification |

### Key Architectural Recommendations

1. **Automate the refresh pipeline** (Phase 5B, P0). Implement cron-based or CI-triggered weekly re-ingestion for all sources. Include staleness alerts when sources exceed their recommended refresh cadence.

2. **Ingest the remaining configured sources.** Run first ingestion for EEOC, Legal Aid at Work, P2 statutory codes, CCR regulations, and DLSE sources. These are configured but appear not yet in the active knowledge base.

3. **Fix the CalHR oversized chunk.** Implement max-chunk-size enforcement in the heading-based chunker to split chunks exceeding the token limit.

4. **Investigate DIR crawl errors.** 10% error rate (30/300 URLs) is too high. May indicate broken links, timeouts, or selector issues.

5. **Consider official CCR source.** Cornell LII is a mirror. For a legal product, consider scraping directly from OAL or using an official data feed to ensure regulatory text is current.

6. **Add staleness metadata to answers.** When a source chunk's ingestion date exceeds the recommended refresh cadence, flag it in the answer. E.g., "Note: This statutory text was last verified on [date]."

7. **Discovery module integration.** The discovery generator (FROGS, SROGS, RFPD, RFA templates) currently does NOT reference the knowledge base. Consider feeding relevant statutory citations from the knowledge base into discovery templates to improve accuracy and reduce hallucination risk in generated discovery requests.

---

## Knowledge Source Refresh Pipelines — Implementation Plan

> **Date:** 2026-03-04
> **Status:** Tier 1 IMPLEMENTED. Tiers 2–4 planned.

### Overview

This section defines the implementation plan for building automated refresh pipelines that keep each knowledge source up to date. The plan is organized by the same source tiers defined above, reflecting data criticality and refresh complexity.

### What Already Exists (Not Duplicated)

The following infrastructure is **already built and working** — the refresh pipeline builds ON TOP of it:

- **Extraction**: PubinfoLoader, StatutoryExtractor, CACILoader, CCR loaders, DLSE loaders, OpinionLoader, Playwright crawler — all functional
- **Chunking**: `section_boundary` (statutory) and `heading_based` (agency) strategies — both working
- **Storage**: SQLite with content-hash deduplication, soft-delete, run tracking — fully operational
- **CLI surface**: `scrape`, `refresh`, `pubinfo-download`, `embed`, `embed-status`, `cross-validate`, `ingest-caselaw` — all implemented
- **Vector indexing**: LanceDB with hybrid search, BM25 FTS, RRF — complete
- **Retry/resilience**: Extraction-level exponential backoff, circuit breaker, rate limiting — in place

### What's Missing (What We're Building)

| Gap | Impact |
|-----|--------|
| **No scheduling** — all refreshes are manual CLI commands | Sources go stale until someone remembers to run them |
| **No staleness detection** — no tracking of when each source was last successfully refreshed | No way to know if data is outdated |
| **No scrape→embed orchestration** — embedding is a separate manual step after scraping | New/updated content invisible to search until manually embedded |
| **No change reporting** — refreshes run silently | No visibility into what changed, what's new, what was repealed |
| **No pipeline-level error recovery** — extraction retries exist, but pipeline failures require full re-run | A single network blip during a 40-minute agency crawl wastes the entire run |
| **No health dashboard** — minimal `/api/health` endpoint | Ops blindness: is the knowledge base healthy? fresh? complete? |

---

### Software Architect Review

#### Diagnosis: Current Pipeline Architecture

The `Pipeline` class (`pipeline.py`, 903 lines) began as a single-responsibility web crawler orchestrator (Phase 1). Successive additions — statutory extraction (Phase 1.5C), CACI, DLSE, CCR, and case law — evolved it into a multi-purpose orchestrator with three distinct code paths and significant duplication. This assessment identifies what must be fixed during Tier 1, what should be deferred, and proposes a universal framework that all tiers will share.

**Hard Violations (Fix in Tier 1):**

| # | Smell | Location | Impact on Tier 1 |
|---|-------|----------|-------------------|
| D1 | **G5 — Duplication**: Document-upsert + chunk-insert pattern (~20 lines) is copy-pasted in `_run_statutory:436-466`, `_run_caselaw:608-636`, `_run_crawler:827-854` | `pipeline.py` | The `UpsertStatus` enum (T1-B.3) must update all 3 call sites. Extract a shared `_persist_document()` method first, then modify once. |
| D2 | **G5 — Duplication**: `PipelineStats` initialization + `complete_run()` + `_log_run_summary()` boilerplate is repeated in all 3 `_run_*` methods | `pipeline.py` | `PipelineStats` extension (T1-B.5) must update all 3. Extract into shared setup/teardown. |

**Soft Smells (Defer to Tier 2–3):**

| # | Smell | Location | Recommendation |
|---|-------|----------|----------------|
| D3 | **G23 — Switch over method**: `_run_statutory` dispatches via 7-branch if/elif on `statutory.method` | `pipeline.py:392-412` | Replace with extraction method registry (dict mapping method name → callable). Address when adding new extraction methods in Tier 2–3. |
| D4 | **LSP — Dummy CrawlConfig**: Non-crawl sources create `CrawlConfig(seed_urls=["https://placeholder.invalid"])` | `pipeline.py:144-152` | Decouple Pipeline from CrawlConfig dependency. Non-crawl paths only use `chunking` and `database_path` — both accessible directly from `SourceConfig`. Address in Tier 3. |
| D5 | **CCP — Mixed responsibilities**: Pipeline.py changes for 3 independent reasons (new extractors, persistence logic, crawler behavior) | `pipeline.py` | Decompose into separate concerns when Tier 3 (Agency/Crawler) refresh adds enough pressure. |

**Root Cause**: Pipeline started as a web crawler. Statutory, CACI, DLSE, CCR, and case law were added incrementally, each copying the working pattern with minor variations. This is classic "successful code evolution" — it worked, and duplication was acceptable during rapid feature delivery. Now that the refresh pipeline touches all paths (via `UpsertStatus`, `PipelineStats`, auto-embed), the duplication impedes safe, single-point changes. The Tier 1 plan is the right moment to extract the shared core.

---

### Universal Refresh Framework

Every knowledge source refresh — statutory, agency, case law, CACI, DLSE, CCR — follows the same 5-step contract. The framework extracts what's shared and defines what varies.

#### The 5-Step Refresh Contract

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  1. CHECK   │──▶│  2. ACQUIRE │──▶│ 3. EXTRACT  │──▶│  4. PERSIST │──▶│  5. INDEX   │
│  Staleness  │   │  Raw Data   │   │  Sections   │   │  Documents  │   │  Vectors    │
│  (shared)   │   │  (varies)   │   │  (varies)   │   │  (shared)   │   │  (shared)   │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
     SKIP if          PUBINFO ZIP      PubinfoLoader     _persist_doc()    Incremental
     fresh            Playwright       CACILoader         UpsertStatus      embed via
     (--if-stale)     CourtListener    OpinionLoader      soft-delete       content_hash
                      HTTP/PDF         HTML/PDF extract   change report     + FTS rebuild
```

| Step | Shared? | What Varies | What's Shared |
|------|---------|-------------|---------------|
| **1. CHECK** | Fully shared | Nothing | `last_refreshed_at` vs `max_age_days` threshold |
| **2. ACQUIRE** | Fully varies | PUBINFO ZIP, Playwright crawl, CourtListener API, PDF download, HTTP scrape | Nothing — each source type has its own acquisition strategy |
| **3. EXTRACT** | Interface shared, impl varies | PubinfoLoader, CACILoader, StatutoryExtractor, DLSEOpinionLoader, OpinionLoader, HTML/PDF extractors | All produce items with: `source_url`, `title`, `raw_content`, `content_hash`, `content_category` |
| **4. PERSIST** | Fully shared | Nothing | `_persist_document()` → `upsert_document()` → `insert_chunks()` → `deactivate_missing_sections()`. Same ~20 lines across all pipelines today — extract once. |
| **5. INDEX** | Fully shared | Nothing | Incremental embed via content_hash delta → upsert LanceDB → rebuild FTS. Already implemented in `_embed_all()`. |

#### Framework Implementation Strategy

The framework is NOT a new module, class hierarchy, or Big Bang refactor. It's a targeted extraction of shared logic from the existing `Pipeline` class, implemented incrementally during Tier 1.

**Tier 1 Extractions (framework scaffolding):**

1. **Extract `_persist_document()`** (T1-B.3): Pull the duplicated upsert+chunk pattern from all three `_run_*` methods into one shared private method. This is the minimum viable refactor that unblocks `UpsertStatus` AND reduces duplication from 60 lines (3 × 20) to 20 lines (1 × 20). All three pipelines call the same method.

2. **Extract stats setup/teardown** (T1-B.5): Pull `PipelineStats` initialization, `create_run()`, `complete_run()`, and `_log_run_summary()` into a shared pattern (context manager or setup method). Extending `PipelineStats` then requires changes in one place.

3. **Shared orchestration in `refresh` CLI** (T1-B.6–B.8): The `--tier` filter, `--auto-embed`, `--if-stale` flags, and change reporting are tier-agnostic. They work identically for all source types.

**Tier 2–3 Extractions (framework refinement):**

4. **Extraction method registry** (Tier 2): Replace the if/elif chain with a dict mapping `statutory.method` → callable. Adding a new extractor becomes registering a function, not modifying `_run_statutory`.

5. **Decouple from CrawlConfig** (Tier 3): Remove the dummy CrawlConfig hack. Non-crawl pipelines take `SourceConfig` directly.

#### What This Framework Means for Each Tier

| Tier | Acquirer (Step 2, varies) | Shared Infrastructure (Steps 1, 4, 5) |
|------|---------------------------|----------------------------------------|
| **T1: Statutory** | PUBINFO ZIP conditional download | Staleness tracking, `_persist_document()`, `UpsertStatus`, auto-embed + FTS rebuild, change reports, source-health |
| **T2: Regulatory** | CCR HTTP scrape, DLSE PDF download, CACI PDF download | Same shared infrastructure from T1. Add extraction method registry. |
| **T3: Agency** | Playwright crawl (DIR, EDD, CalHR) | Same shared infrastructure. Decouple CrawlConfig. Add crawl-specific resume/retry. |
| **T4: Case Law** | CourtListener API | Same shared infrastructure + citation link resolution (already built). |

**Key insight**: The shared infrastructure built in Tier 1 (`_persist_document()`, `UpsertStatus`, `PipelineStats` extension, auto-embed, FTS rebuild, staleness tracking, source-health, change reporting) is used unchanged by Tiers 2–4. Each subsequent tier only needs to:
1. Add a `--tier <name>` filter value
2. Add `refresh.*` config to its source YAMLs
3. (Possibly) add a `download_if_changed()` for its acquirer
4. Test

**This means Tiers 2–4 are significantly smaller than Tier 1.** Most of the work is framework, and Tier 1 builds the framework.

---

### Tier 1: Primary Law (Statutory Codes) — Refresh Pipeline

#### Pressure Test: Assumptions Examined

Before finalizing the implementation plan, the following assumptions were stress-tested through Product Management, Technical Architecture, Software Architecture, and Business Analysis lenses. Several assumptions from the initial draft did not survive scrutiny. The revised plan below reflects these corrections.

---

##### Assumption 1: "We need a new `refresh-statutory` CLI command"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The existing `refresh` command (`cli.py:589-705`) already iterates over sources, runs `Pipeline.run()`, captures before/after counts, and prints a change report. It even has `--source` and `--all` flags. Creating a parallel `refresh-statutory` command duplicates this orchestration logic and creates a maintenance fork — two commands that do nearly the same thing but drift apart over time. The only missing capabilities are: (a) tier-based filtering, (b) auto-download of PUBINFO before statutory sources, (c) auto-embed after scraping. |
| **Product Manager** | From an operator's perspective, having both `refresh` and `refresh-statutory` is confusing. "Which one do I use? When? What's the difference?" A single `refresh` command with flags is simpler to document, teach, and script. |
| **Resolution** | **Don't create `refresh-statutory`.** Extend the existing `refresh` command with: `--tier statutory` filter (runs only statutory sources), `--auto-download` (conditionally fetches PUBINFO before statutory runs), `--auto-embed` (runs incremental embedding after scraping), and `--if-stale` (skips sources that are still fresh). This keeps the CLI surface unified and builds on code that already works. |

##### Assumption 2: "We can distinguish new sections from amended sections"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The plan's change report (originally T1-C.2) promises separate counts for "new sections," "updated sections," and "repealed sections." But `upsert_document()` (`storage.py:303-340`) returns only `(doc, is_new_or_changed: bool)`. It returns `True` for both a brand-new section AND a section whose content_hash changed (an amendment). The method deletes the old document+chunks and inserts fresh — it doesn't distinguish creation from update. |
| **Technical Architect** | To distinguish new from amended, we'd need to pre-check existence before calling upsert — an extra DB query per document (20K+ queries for a full statutory refresh). Alternatively, we'd need to change `upsert_document()` to return a 3-state enum (`NEW`/`UPDATED`/`UNCHANGED`). Both approaches add complexity. |
| **Business Analyst** | Does the operator actually need to know the difference? The question "did this section change?" is more actionable than "is this section new or amended?" An operator's response is the same either way: verify the content looks correct. The repealed/deactivated distinction IS important (a section disappearing has different implications than one changing). |
| **Resolution** | Modify `upsert_document()` to return a status enum with three states: `NEW`, `UPDATED`, `UNCHANGED`. This is a clean, low-cost change (check existence before the insert, which it already does). Report "new + changed" as one category if desired, but capture the distinction in the data for future use. Repealed sections are already tracked separately via `deactivate_missing_sections()`. |

##### Assumption 3: "We can detect which sections were repealed"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | `deactivate_missing_sections()` (`storage.py:433-455`) returns only an `int` count. The plan assumed it could report which specific sections were deactivated. To get details, we need to modify the method to return structured data: `list[DeactivatedSection]` with `{source_url, document_id, chunks_deactivated, citation}`. |
| **Resolution** | Modify `deactivate_missing_sections()` to return a list of `{source_url, chunks_deactivated}` dicts in addition to (or replacing) the integer count. This is a small, safe change — the method already iterates over documents internally. |

##### Assumption 4: "An `embedded_at` column is needed for incremental embedding"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The plan proposed adding `embedded_at` to the chunks table to track which chunks need embedding. But the codebase already has a working incremental embedding mechanism: `_embed_all()` (`cli.py:888-947`) calls `vector_store.get_embedded_content_hashes()`, compares against chunk content_hashes, and embeds only the delta. It also syncs deactivated chunks (removes inactive chunk IDs from LanceDB). This is exactly what the plan proposed building — **it already exists.** |
| **Technical Architect** | Adding `embedded_at` to SQLite creates a dual-truth problem: SQLite says "embedded at 3pm" but LanceDB might not have the vector (if LanceDB was rebuilt, or the upsert failed silently). The existing approach — where LanceDB itself is the source of truth for "what's embedded" — is architecturally cleaner. |
| **Business Analyst** | The real gap isn't "knowing what to embed" (already solved). It's "automatically embedding after a refresh" (currently requires a separate manual `embed` command). The fix is orchestration, not tracking. |
| **Resolution** | **Don't add `embedded_at`.** The existing `_embed_all()`/`_embed_source()` functions already do incremental embedding via content_hash comparison. The only needed change is wiring this into the `refresh` command via an `--auto-embed` flag that calls the existing embed logic after scraping completes. |

##### Assumption 5: "A scheduler daemon is the right automation approach"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | The current deployment is a **single stateless uvicorn container on Railway** (`Dockerfile` → `CMD uvicorn ...`). A long-running scheduler daemon would require either: (a) a second Railway service (doubles hosting cost), (b) an embedded scheduler in the FastAPI process (couples concerns, unreliable — container restarts kill the scheduler, no persistence), or (c) APScheduler with a database-backed job store (heavy dependency for one cron job). None of these are good fits for the current architecture. |
| **Product Manager** | We have exactly one operator (the PO). The statutory codes change primarily once per year (January 1). Building a persistent daemon scheduler for a weekly check of an annual dataset is significant over-engineering. A calendar reminder + manual command achieves 90% of the value. The `--if-stale` flag with external cron gets to 99%. |
| **Business Analyst** | The risk window for stale statutory content is narrow: late December through early January when annual code updates take effect. Urgency statutes (immediately effective) are rare and mostly non-employment. A monthly manual refresh is sufficient to catch urgency statutes within an acceptable window. |
| **Resolution** | **Don't build a scheduler daemon.** Instead: (1) Implement `--if-stale` flag on the `refresh` command (runs only if any source exceeds its `max_age_days`). (2) Provide a GitHub Actions workflow for scheduled refresh (cron-triggered, runs in CI). (3) The existing CLI is the automation interface — external cron calls `employee-help refresh --tier statutory --auto-embed --if-stale`. This is simpler, more reliable, and costs nothing extra to operate. |

##### Assumption 6: "Webhook notifications are needed"

| Lens | Challenge |
|------|-----------|
| **Product Manager** | Who receives the notifications? There is one operator. Building a `Notifier` class with `LogNotifier` and `WebhookNotifier` implementations, a config section for webhook URLs, and a notification dispatch system is infrastructure for a team that doesn't exist. Structured log output captured by cron (or GitHub Actions logs) is sufficient for a single-operator system. |
| **Software Architect** | The notification dispatcher introduces a new module (`notifications.py`), a new config section, a new dependency surface (webhook HTTP calls that can fail), and new error handling (what if the notification fails?). All of this for log output that `structlog` already provides. |
| **Resolution** | **Don't build a notification system.** The `refresh` command already prints a change report to stdout. Structured logs via `structlog` are sufficient. If the PO wants email/Slack alerts, GitHub Actions has built-in notification support for failed workflow runs. Revisit when there's a team or when the system is monitored by external ops tooling. |

##### Assumption 7: "Error isolation should be a later phase"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The original plan had error isolation (T1-G) as phase 7 of 8, depending on T1-C. But the existing `_refresh_all_sources()` (`cli.py:643-669`) **already has basic error isolation** — it wraps each source in try/except and counts errors. If we're extending `refresh` rather than creating a new command, we inherit this. The gap isn't "add error isolation" — it's "improve the error reporting within the isolation that exists." |
| **Technical Architect** | Error isolation is a prerequisite for reliability, not an afterthought. If the unified refresh command runs 9 statutory sources and source #3 crashes the process, sources 4-9 never run. This should be built into the command from day one, not retrofitted 6 phases later. |
| **Resolution** | **Error isolation is built into the refresh command from the start** (it already exists in the current code). Enhance it with: retry-once for failed sources, and structured error details in the change report. This is part of T1-B (the unified command phase), not a separate phase. |

##### Assumption 8: "The PUBINFO HTTP HEAD request will work for conditional downloads"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | Government servers often don't return reliable `Last-Modified` or `ETag` headers. The plan assumes the leginfo download server supports conditional requests. If it doesn't return useful headers, the entire conditional download mechanism is useless. This must be verified before building around it. |
| **Resolution** | **Spike first.** Before implementing conditional download, send a manual HTTP HEAD to `https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip` and verify that `Last-Modified` and/or `Content-Length` headers are returned. If they are, use them. If not, fall back to comparing local file size and mod-time against the remote `Content-Length` header, or simply re-download weekly (677MB is manageable on a weekly cadence). Build the conditional logic defensively with a fallback to forced download. |

##### Assumption 9: "FTS index is handled by incremental embedding"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | After `vector_store.upsert_embeddings()`, the LanceDB FTS (BM25) index is marked dirty (`_fts_dirty = True`) but NOT rebuilt. Hybrid search relies on both vector similarity AND BM25 full-text matching. If new chunks are embedded but the FTS index isn't rebuilt, hybrid search will miss them on the BM25 side — the new chunks are vector-searchable but text-invisible. The plan never mentions FTS rebuild. |
| **Business Analyst** | This is a silent correctness bug. An attorney searching for "Lab. Code § 1102.5" after a refresh that added new sections would get vector matches (similar content) but might miss the exact BM25 match for the new section number. This degrades retrieval quality without any visible error. |
| **Resolution** | **Add explicit FTS rebuild as a post-embed step.** After incremental embedding completes, call `vector_store.rebuild_fts_index()`. This is cheap (~1-2 minutes for 24K rows) and ensures hybrid search consistency. Include this in the `--auto-embed` flow. |

##### Assumption 10: "Consecutive failure tracking needs a DB column"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | Tracking consecutive failures in the `sources` table adds schema complexity for a situation that should be rare (PUBINFO downloads are reliable). The `crawl_runs` table already stores run status per source with timestamps. Consecutive failures can be derived: `SELECT COUNT(*) FROM crawl_runs WHERE source_id = ? AND status = 'failed' AND completed_at > (SELECT MAX(completed_at) FROM crawl_runs WHERE source_id = ? AND status = 'completed')`. No new columns needed. |
| **Resolution** | **Derive consecutive failures from `crawl_runs` instead of adding a column.** Add a `get_consecutive_failures(source_id)` query to Storage. Display in `source-health` output. No schema migration needed. |

---

#### Revised Plan (Post Pressure-Test)

After pressure-testing, the plan reduces from **8 phases / ~68 tests** to **5 phases / ~50 tests**. Key changes:

- `refresh-statutory` dropped — extend existing `refresh` command instead
- `embedded_at` column dropped — existing LanceDB content_hash dedup is sufficient
- Scheduler daemon dropped — `--if-stale` + external cron (GitHub Actions)
- Webhook notifications dropped — stdout + structlog + GitHub Actions alerts
- Error isolation moved earlier — built into the command from day one
- FTS rebuild added — critical for hybrid search correctness
- PUBINFO HEAD request requires spike verification

---

#### Phase T1-A: Staleness Tracking & Source Health

> **Goal**: Make staleness visible. Know when each source was last refreshed and whether the data is stale.
>
> **Why first**: This is the highest-value work. If an attorney gets a citation to a repealed statute, trust is destroyed. Before we can automate refreshes, we need to see what's stale.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T1-A.1 | **Add `last_refreshed_at` to sources table** | Add a nullable `last_refreshed_at` timestamp column to `sources`. Update `Pipeline.run()` to set this on successful completion. Add `Storage.get_source_freshness()` returning `{slug, last_refreshed_at, age_days}` per source. Note: can also be derived from `crawl_runs.completed_at` but a denormalized column avoids a join on every health check. Schema migration needed for existing production DB. | `storage.py` |
| T1-A.2 | **Add staleness thresholds to source configs** | Add optional `refresh.max_age_days` to each source YAML. Defaults: 7 (statutory), 14 (agency), 30 (case law), 180 (CACI/DLSE manual). Add `RefreshConfig` dataclass to config loader. Update all 21 source YAMLs (or rely on per-type defaults). | `config/sources/*.yaml`, config loader |
| T1-A.3 | **Implement `source-health` CLI command** | New CLI: `employee-help source-health`. Table output: slug, last_refreshed_at, age (days), max_age, status (FRESH/STALE/NEVER_RUN). Derive consecutive failures from `crawl_runs` table (no new column). Add `--json` for machine-readable output. | T1-A.1, T1-A.2 |
| T1-A.4 | **Add freshness to `/api/health` endpoint** | Extend health response: `sources_stale: int`, `oldest_source: {slug, age_days}`. If any source exceeds `max_age_days`, return `"knowledge_base": "stale"`. | T1-A.1, T1-A.2, `api/routes.py` |
| T1-A.5 | **[GATE]** `source-health` shows correct freshness for all sources. `/api/health` reports staleness accurately. Consecutive failure derivation works against `crawl_runs`. | T1-A.1–T1-A.4 |

**Tests**: `get_source_freshness()` with various timestamps, staleness threshold parsing from YAML, health endpoint with stale/fresh sources, consecutive failure derivation. ~10 tests.

---

#### Phase T1-B: Enhanced Refresh with Change Reporting & Orchestration

> **Goal**: A single `refresh` command that handles the full lifecycle: conditional PUBINFO download → scrape → report changes → embed → FTS rebuild.
>
> **Why this combines several original phases**: Error isolation already exists in `_refresh_all_sources()`. Change detection is a natural extension of the existing refresh report. Auto-embed is orchestration wiring, not new embed logic. Splitting these into 4 separate phases would create artificial gates between tightly coupled changes.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T1-B.1 | **Spike: PUBINFO conditional download feasibility** | Send HTTP HEAD to `https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip`. Verify `Last-Modified` and/or `Content-Length` headers are returned. Document findings. If headers are unreliable, fall back to file-size comparison or always-download. This is a spike, not production code — 30 minutes of investigation. | — |
| T1-B.2 | **Implement conditional PUBINFO download** | Based on spike results: add `download_if_changed()` to PubinfoLoader. Store `{last_modified, content_length, downloaded_at}` in `.pubinfo_meta.json`. If headers match, skip download. If HEAD fails or headers are missing, fall back to forced download. Validate ZIP integrity after download (check CRC, verify `LAW_SECTION_TBL.dat` exists). Never overwrite a good archive with a corrupt download. Add `--check-only` flag to `pubinfo-download` CLI. | T1-B.1 |
| T1-B.3 | **Extract `_persist_document()` + add `UpsertStatus`** | **Framework task (D1 fix).** First, extract the duplicated document-upsert + chunk-insert pattern from `_run_statutory:436-466`, `_run_caselaw:608-636`, and `_run_crawler:827-854` into a single shared `_persist_document()` method on Pipeline. Then change `upsert_document()` return type from `(Document, bool)` to `(Document, UpsertStatus)` where `UpsertStatus` is an enum: `NEW`, `UPDATED`, `UNCHANGED`. The extraction MUST happen before the enum change — otherwise we modify 3 call sites instead of 1. This is the minimum viable refactor that fixes D1 and unblocks change reporting. | `storage.py`, `pipeline.py` |
| T1-B.4 | **Modify `deactivate_missing_sections()` to return details** | Change return from `int` to `list[dict]` with `{source_url, document_id, chunks_deactivated}`. The method already iterates over documents — capture the details instead of just counting. | `storage.py` |
| T1-B.5 | **Extract stats boilerplate + extend `PipelineStats`** | **Framework task (D2 fix).** Extract the repeated `PipelineStats` init → `create_run()` → `complete_run()` → `_log_run_summary()` pattern from all three `_run_*` methods into a shared setup/teardown (context manager or method pair). Then add fields: `new_documents: int`, `updated_documents: int`, `deactivated_sections: list[dict]`, `new_urls: list[str]`, `updated_urls: list[str]`. Populate from `_persist_document()` status (T1-B.3) and `deactivate_missing_sections()` details (T1-B.4). | T1-B.3, T1-B.4, `pipeline.py` |
| T1-B.6 | **Add `--tier` flag to `refresh` command** | Add `--tier statutory|agency|regulatory|caselaw` filter to `refresh`. Filters `load_all_source_configs()` by source_type. `--tier statutory` runs only the 9 PUBINFO-based sources. Combine with existing `--all` flag: `refresh --all --tier statutory`. | `cli.py` |
| T1-B.7 | **Add `--auto-download` flag to `refresh` command** | When `--auto-download` is set and any statutory sources are in the refresh set, run conditional PUBINFO download (T1-B.2) before starting source refreshes. Skip download if not refreshing any statutory sources. | T1-B.2, T1-B.6, `cli.py` |
| T1-B.8 | **Add `--auto-embed` flag to `refresh` command** | After all sources are refreshed, if any had changes (new_documents > 0 or updated_documents > 0 or deactivated > 0), run the existing `_embed_source()` or `_embed_all()` logic for affected sources. Skip if no changes detected. After embedding, call `vector_store.rebuild_fts_index()` to keep BM25 in sync. Add `--skip-embed` to explicitly disable. | `cli.py`, existing embed logic |
| T1-B.9 | **Enhance refresh report with change details** | Extend `_print_refresh_report()` to show: new sections (count + sample URLs), updated sections (count + sample URLs), deactivated sections (count + citations), embed status (skipped/N chunks embedded), FTS rebuild status. Write JSON report to `data/refresh_reports/YYYY-MM-DD_HH-MM.json` for audit trail. | T1-B.5, T1-B.8 |
| T1-B.10 | **Improve error isolation and retry** | Enhance existing try/except in `_refresh_all_sources()`: (a) After first pass, retry any FAILED sources once with a 5-second delay. (b) Include per-source error details in the change report JSON. (c) Final exit code is 0 only if all sources succeeded (including retries). | `cli.py` |
| T1-B.11 | **[GATE]** `refresh --all --tier statutory --auto-download --auto-embed` runs end-to-end. On unchanged data: 0 new, 0 updated, 0 deactivated, embed skipped. Dry-run produces report without modifying DB. Error in one source doesn't abort others. Change report JSON is written. FTS index is rebuilt after embed. | T1-B.1–T1-B.10 |

**Tests**: `_persist_document()` extraction (verify all 3 pipeline paths use it, verify identical behavior). Conditional download (mock HEAD, skip/download logic, ZIP validation). `UpsertStatus` enum behavior for new/updated/unchanged. `deactivate_missing_sections` detail return. Stats setup/teardown extraction. `--tier` filter. `--auto-download` with/without statutory sources. `--auto-embed` with changes/no-changes. FTS rebuild after embed. Retry logic. Change report JSON schema. ~28 tests.

**Framework contribution**: T1-B.3 and T1-B.5 are framework tasks that fix D1 and D2 (duplicated code). Once extracted, Tiers 2–4 get `_persist_document()` and the extended `PipelineStats` for free — no per-tier modification needed.

---

#### Phase T1-C: Scheduling via External Cron

> **Goal**: Statutory refreshes run on schedule without human intervention, using external scheduling (not an in-process daemon).
>
> **Why external cron, not a daemon**: The deployment is a stateless Railway container. A daemon requires a second service (doubles cost) or an embedded scheduler (unreliable). `--if-stale` + external cron is simpler, cheaper, and more reliable.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T1-C.1 | **Add `--if-stale` flag to `refresh` command** | When set, the refresh command checks each source's `last_refreshed_at` against its `max_age_days` threshold (from T1-A). Sources that are still fresh are skipped with a log message. Only stale or never-run sources are refreshed. This makes the command safe to run frequently — it's a no-op when everything is fresh. | T1-A.1, T1-A.2 |
| T1-C.2 | **Create GitHub Actions workflow for scheduled refresh** | `.github/workflows/refresh.yml`: cron-triggered (e.g., `0 3 * * 0` — Sunday 3am UTC). Steps: checkout → install uv → `employee-help refresh --all --tier statutory --auto-download --auto-embed --if-stale`. Workflow uses repository secrets for `ANTHROPIC_API_KEY` (if embed needs it — check if embedding is purely local). Captures refresh output as workflow artifact. Sends GitHub notification on failure. | T1-B, T1-C.1 |
| T1-C.3 | **Add refresh schedule reference to source configs** | Add optional `refresh.cron_hint` field to source YAMLs. This is documentation-only (not parsed by code): `cron_hint: "0 3 * * 0"  # Sunday 3am UTC`. Helps operators know the intended cadence when reviewing configs. | `config/sources/*.yaml` |
| T1-C.4 | **[GATE]** `refresh --if-stale` correctly skips fresh sources and runs stale ones (tested by setting `last_refreshed_at` to old timestamp). GitHub Actions workflow runs successfully in CI (dry-run mode for gate test). | T1-C.1–T1-C.3 |

**Tests**: `--if-stale` with mock freshness data (fresh → skip, stale → run, never_run → run). ~5 tests.

---

#### Phase T1-D: Observability & Run History

> **Goal**: The operator can see what happened after each refresh without digging through raw logs.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T1-D.1 | **Add run history to `source-health` output** | Extend `source-health` to show last 3 refresh runs per source: date, duration, status (completed/failed), changes (new/updated/deactivated counts). Add `--history <n>` flag. Data comes from `crawl_runs` table (summary JSON + status). | T1-A.3 |
| T1-D.2 | **Add `/api/refresh-status` endpoint** | New API endpoint returning: per-source freshness, last run result, next scheduled refresh hint (from `cron_hint` in config), overall knowledge base health score. Useful for ops dashboard or uptime monitoring. | T1-A.4, T1-B.9 |
| T1-D.3 | **[GATE]** `source-health --history 5` shows accurate run history. `/api/refresh-status` returns correct state. Change report JSON files accumulate in `data/refresh_reports/` across multiple runs. | T1-D.1–T1-D.2 |

**Tests**: Run history query against `crawl_runs`. API endpoint response schema. ~5 tests.

---

#### Phase T1-E: Validation & Acceptance

> **Goal**: Verify the entire pipeline end-to-end and get PO sign-off.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T1-E.1 | **End-to-end integration test** | Run `refresh --all --tier statutory --auto-download --auto-embed` against the real PUBINFO archive. Verify: conditional download, all 9 sources refresh, change report generated, embed runs (or skips), FTS rebuilt, `source-health` shows FRESH. | All T1 phases |
| T1-E.2 | **Simulated change test** | Use fixture data to simulate: (a) new section added, (b) existing section amended (content_hash changed), (c) section repealed (removed from PUBINFO). Verify change report accurately reflects all three. Verify embed processes only changed chunks. Verify deactivated chunks removed from LanceDB. | All T1 phases |
| T1-E.3 | **Documentation** | Update KNOWLEDGE.md with: final architecture diagram, operational runbook (manual refresh, cron setup, troubleshooting), config reference for `refresh.*` fields in source YAMLs. | All T1 phases |
| T1-E.4 | **[GATE]** PO approves Tier 1 pipeline. Statutory sources can be refreshed via a single command or automated cron. Changes are tracked, reported, and embedded. Errors are isolated and retried. The operator has visibility into knowledge base health. | T1-E.1–T1-E.3 |

**Tests**: E2E integration (marks as `@pytest.mark.slow`). Simulated change scenarios. ~5 tests.

---

#### Revised Tier 1 Summary

| Phase | Focus | Est. Tests | Key Deliverable | Framework? |
|-------|-------|-----------|-----------------|------------|
| **T1-A** | Staleness tracking & source health | ~10 | `source-health` CLI, health endpoint freshness | Yes — all tiers use staleness thresholds |
| **T1-B** | Enhanced refresh with orchestration | ~28 | `_persist_document()`, `UpsertStatus`, `--tier`, `--auto-embed`, change reports | Yes — D1/D2 fixes, shared by all tiers |
| **T1-C** | External cron scheduling | ~5 | `--if-stale` flag, GitHub Actions workflow | Yes — cron works for all tiers |
| **T1-D** | Observability & run history | ~5 | Run history in CLI, `/api/refresh-status` | Yes — source-agnostic |
| **T1-E** | Validation & acceptance | ~5 | E2E tests, documentation, PO sign-off | — |
| **Total** | | **~53** | Fully automated statutory refresh pipeline + universal framework | |

**Reduction from initial plan:** 8 phases → 5. ~68 tests → ~53. Eliminated: redundant CLI command, `embedded_at` schema change, scheduler daemon, webhook notifications. Added: FTS rebuild, PUBINFO HEAD spike, `UpsertStatus` enum, `_persist_document()` extraction (D1), stats boilerplate extraction (D2).

#### Revised Dependencies & Sequencing

```
T1-A (staleness) ──→ T1-B (enhanced refresh + orchestration)
                            │
                            ├──→ T1-C (cron scheduling)
                            │
                            └──→ T1-D (observability)
                                    │
                                    └──→ T1-E (validation & acceptance)
```

T1-A is prerequisite for T1-B (need freshness tracking before `--if-stale`). T1-B is the bulk of the work and can gate on A's completion. T1-C and T1-D are independent of each other and can be developed **in parallel** after T1-B. T1-E is the final integration gate.

---

#### Key Risks (Post Pressure-Test)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **PUBINFO HEAD request unreliable** | Medium | T1-B.1 spike verifies before building. Fallback: always download (677MB weekly is acceptable). |
| **`UpsertStatus` change breaks callers** | Low | T1-B.3 extracts `_persist_document()` first, reducing from 3 call sites to 1. Old `bool` callers in tests can check `status != UNCHANGED`. |
| **Schema migration on production DB** | Medium | `last_refreshed_at` is nullable, so `ALTER TABLE ADD COLUMN` works without backfill. Test migration against a copy of production DB first. |
| **GitHub Actions cron requires repo secrets** | Low | Embedding model is local (bge-base-en-v1.5, no API key needed). Only `COURTLISTENER_API_TOKEN` matters, and that's Tier 4. |
| **FTS rebuild during active queries** | Low | LanceDB FTS rebuild is atomic (creates new index, swaps). No read contention. |
| **SQLite WAL contention during refresh** | Low | WAL mode supports concurrent reads during writes. Refresh writes are short bursts per source (~22s each). Web server queries are read-only. No conflict expected at current scale. |
| **`_persist_document()` extraction breaks behavior** | Low | Extract-then-verify: write the shared method, update one `_run_*` path, run existing tests, then update remaining paths. Existing 1,535 tests provide safety net. The extraction is a pure refactor — zero behavior change. |

---

#### Architectural Debt Ledger

The following items are explicitly deferred. Each has a trigger condition for when it should be addressed.

| Debt Item | Severity | Trigger | Target Tier |
|-----------|----------|---------|-------------|
| D3: Extraction method switch statement (OCP violation) | Soft | Adding 2+ new extraction methods | Tier 2 |
| D4: Dummy CrawlConfig for non-crawl sources (LSP) | Soft | Next modification to Pipeline.__init__ for non-crawl sources | Any |
| D5: Pipeline.py mixed responsibilities (CCP) | Soft | Pipeline.py exceeds ~1200 lines or changes for 3+ reasons in one sprint | Tier 3 |

These are conscious, bounded decisions — not ignored debt. Each has a clear payback trigger.

---

### `--tier` Filter Implementation Note

The tier filter maps tier names to `content_category` values, directly implementing the documented authority hierarchy (no config changes needed):

```python
_TIER_CATEGORIES = {
    "statutory": {"statutory_code"},
    "regulatory": {"regulation", "jury_instruction"},
    "persuasive": {"opinion_letter", "enforcement_manual", "federal_guidance"},
    "agency": {"agency_guidance", "fact_sheet", "faq", "legal_aid_resource", "poster"},
    "caselaw": {"case_law"},
}
```

This is implemented once in T1-B.6 and works for all tiers without modification. Each source's `extraction.content_category` in its YAML determines which tier filter captures it.

---

### Tier 2: Binding Regulations & Quasi-Authoritative — Refresh Pipeline

**Sources**: CCR Title 2 (FEHA regs), CCR Title 8 (Industrial Relations), CACI Jury Instructions
**Extraction methods**: `ccr_web`, `ccr_title_8` (Cornell LII scrape), `caci_pdf` (local PDF)
**All 3 sources already ingested.** This tier is primarily configuration + validation.

#### Pressure Test: Assumptions Examined

##### Assumption 1: "CCR sources need monthly refresh"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | CCR regulatory changes go through OAL formal rulemaking (public comment, review period, OAL approval). Employment regulation changes are infrequent — FEHA regulations had their last major update in 2016 (pregnancy disability leave), with minor updates in 2019 (harassment training). A monthly cadence checks ~160 Cornell LII URLs (~5 minutes wall clock) for changes that happen every few years. |
| **Technical Architect** | With `--if-stale`, monthly cron is a cheap no-op when nothing changed. The cost is only the HTTP requests + content_hash comparison. If Cornell LII is unavailable, existing cached HTML in `data/ccr/` prevents data loss — the CCRLoader uses local cache. |
| **Resolution** | **Monthly cadence is acceptable.** `max_age_days: 30` for CCR sources. The actual HTTP cost is low, and `--if-stale` prevents redundant runs. |

##### Assumption 2: "CACI PDF download can be automated"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | The Judicial Council publishes at predictable URLs with year in filename (`caci_{year}.pdf`). We could check for the next year's file. But the exact month varies (November main edition, May/July supplement), and naming conventions could change. Building URL prediction logic is fragile automation for a twice-yearly event. |
| **Product Manager** | The CACI PDF is manually downloaded today. The gap is not "download the PDF automatically" — it's "know when a new edition exists." An HTTP HEAD check on the predicted URL is sufficient to alert the operator. Manual download remains the trigger; the refresh pipeline handles everything after. |
| **Resolution** | **Don't automate CACI PDF download.** Add a check to `source-health --check-updates` that performs an HTTP HEAD on the predicted next-edition URL and reports "new edition available" or "current edition." Operator manually downloads, then `refresh --source caci --auto-embed` does the rest. |

##### Assumption 3: "D3 (extraction method registry) should be built in T2"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | The if/elif chain in `_run_statutory` (7 branches) is a soft OCP violation. But T2 isn't adding new extraction methods — it's running existing ones through the refresh pipeline. The switch statement doesn't cause friction unless a new method is added. YAGNI says don't fix it until there's pressure. |
| **Pragmatic Programmer** | However, the switch statement creates cognitive load: modifying one branch requires understanding all 7 (Clausen: "code intimacy expires after ~6 weeks"). The registry isolates each branch so changes to one don't risk regressions in others. |
| **Resolution** | **Keep D3 optional in T2.** If T2 testing reveals a regression or confusion caused by the switch complexity, implement the registry. Otherwise, defer to when a new extraction method is needed. |

---

#### Phase T2-A: Configuration & Framework Integration

> **Goal**: All Tier 2 sources work through the unified refresh pipeline built in T1.
>
> **Why this is mostly configuration**: The framework (staleness, change reports, auto-embed, FTS rebuild) was built in T1. T2 just needs `max_age_days` values in YAMLs and verification that existing extractors work through `refresh --tier regulatory`.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T2-A.1 | **Add refresh config to Tier 2 source YAMLs** | Add `refresh.max_age_days` to `ccr_title2_feha.yaml` (30), `ccr_title_8.yaml` (30), `caci.yaml` (180). Add `refresh.cron_hint` documentation fields. | T1-A.2 |
| T2-A.2 | **Validate `--tier regulatory` filter** | Verify `--tier regulatory` captures CCR Title 2, CCR Title 8, and CACI based on their content_category values (`regulation`, `jury_instruction`). Ensure no statutory_code sources are inadvertently included. | T1-B.6 |
| T2-A.3 | **Validate CCR refresh through unified pipeline** | Run `refresh --source ccr_title2_feha --auto-embed`. Verify: change report shows 0 new/0 updated (stable corpus), FTS rebuilt, `source-health` shows FRESH. Then modify one cached HTML file in `data/ccr/` to simulate a regulation change, re-run, verify change is detected and reported. | T2-A.1, T1-B |
| T2-A.4 | **Validate CACI refresh through unified pipeline** | Run `refresh --source caci --auto-embed`. Verify: change report accurate, `source-health` shows FRESH. CACI re-parses the same PDF on every run — verify content_hash dedup means 0 changes on unchanged PDF. | T2-A.1, T1-B |
| T2-A.5 | **[GATE]** `refresh --all --tier regulatory --auto-embed --if-stale` runs all 3 sources end-to-end. Stale sources refresh, fresh sources skip. Change reports accurate. `source-health` shows correct freshness. | T2-A.1–T2-A.4 |

**Tests**: Tier filter captures correct sources (content_category mapping). CCR change detection (mock modified cached HTML). CACI idempotent re-parse (content_hash match). ~8 tests.

---

#### Phase T2-B: CACI Edition Detection

> **Goal**: The operator knows when a new CACI edition is available without manually checking the Judicial Council website.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T2-B.1 | **Add CACI edition check to `source-health`** | When showing CACI health, send HTTP HEAD to predicted next-edition URL (e.g., `caci_{current_year + 1}.pdf` or supplement URL on `courts.ca.gov`). Display "New edition available" if HTTP 200, "Current edition" if 404. This is advisory only — operator still manually downloads. | T1-A.3 |
| T2-B.2 | **Add `--check-updates` flag to `source-health`** | Opt-in flag that performs HTTP checks for sources with predictable download URLs (CACI PDF, DLSE Manual PDF). Without this flag, skip HTTP checks (keeps `source-health` fast and offline-capable). | T2-B.1 |
| T2-B.3 | **[GATE]** `source-health --check-updates` correctly detects CACI edition availability. No false positives on stable editions. Graceful handling of HTTP errors (timeout, 500). | T2-B.1–T2-B.2 |

**Tests**: Mock HEAD for CACI URL (200 = new edition, 404 = current, 500 = unknown). Flag absent = no HTTP check. ~4 tests.

**Framework contribution**: `--check-updates` is reusable — any source with a predictable download URL can be checked (DLSE Manual added in T3).

---

#### Phase T2-C: Extraction Method Registry (D3 Fix — Optional)

> **Goal**: Replace the if/elif chain in `_run_statutory` with a registry pattern, closing the OCP violation.
>
> **Why optional**: This is deferred tech debt from the Architectural Debt Ledger, not a functional requirement. If T2-A testing reveals no issues with the switch statement, skip this phase entirely. Implement when a new extraction method is first needed.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T2-C.1 | **Replace method switch with registry** | Create `_EXTRACTION_METHODS: dict[str, Callable]` mapping method names to extraction callables. Replace the 7-branch if/elif in `_run_statutory` (lines 392-412) with a registry lookup: `extractor = _EXTRACTION_METHODS.get(method)`. Raise `ValueError` for unknown methods. Each existing `_extract_via_*` method becomes a registered entry. Zero behavior change — pure refactor. | `pipeline.py` |
| T2-C.2 | **[GATE]** All 7 existing extraction methods work through registry. Adding a hypothetical new method requires only adding a function + dict entry, not modifying `_run_statutory`. Existing pipeline tests pass unchanged. | T2-C.1 |

**Tests**: Registry lookup for all 7 methods. Unknown method raises ValueError. ~3 tests.

---

#### Tier 2 Summary — **IMPLEMENTED**

| Phase | Focus | Tests | Key Deliverable | Status |
|-------|-------|-------|-----------------|--------|
| **T2-A** | Config + framework integration | 11 | All 3 regulatory sources through refresh pipeline | DONE |
| **T2-B** | CACI edition detection | 6 | `source-health --check-updates` with `check_update_url` | DONE |
| **T2-C** | Extraction method registry (optional) | — | Deferred — no switch issues found | SKIPPED |
| **Total** | | **17** | Automated regulatory refresh pipeline | |

---

### Tier 3: Persuasive Administrative Authority — Refresh Pipeline

**Sources**: DLSE Opinion Letters, DLSE Enforcement Manual, EEOC Federal Guidance
**Extraction methods**: `dlse_opinions` (HTML index + PDFs), `dlse_manual` (single PDF), Playwright crawl (EEOC)
**Key insight**: Two of three sources are effectively static. EEOC uses the same crawl infrastructure as Tier 4 agency sources.

#### Pressure Test: Assumptions Examined

##### Assumption 1: "DLSE Opinion Letters need a refresh pipeline"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | The DLSE opinion letter program is dormant since ~2019. No new letters have been issued in 7 years. This is a closed corpus — the data doesn't change. Building refresh automation for static content is textbook YAGNI. |
| **Software Architect** | The correct approach for a static source is confirmation, not refresh. Verify the corpus hasn't changed (page still accessible, document count stable). If the count changes (unlikely), trigger manual re-ingest. Annual confirmation is sufficient. |
| **Resolution** | **Don't build a refresh pipeline for DLSE opinions.** Add a `refresh.static: true` flag in the source YAML. When `static: true`, the refresh command skips full extraction and performs a lightweight confirmation: verify the index page is reachable, compare stored document count against expected. Report "corpus confirmed" or "corpus changed — manual re-ingest recommended." |

##### Assumption 2: "DLSE Enforcement Manual needs periodic re-download"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | Last updated May 2020 (COVID leave provisions). Years between revisions. The manual is a single PDF (~352 pages). Checking for updates means HTTP HEAD on the download URL and comparing Content-Length or Last-Modified. |
| **Technical Architect** | The `--check-updates` mechanism from T2-B.2 already handles this pattern — sources with predictable download URLs. DLSE Manual fits perfectly: HTTP HEAD on `dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf`, compare against stored metadata. |
| **Resolution** | **Semi-annual check via `source-health --check-updates`** (same mechanism as CACI in T2-B.2). No dedicated pipeline — just `max_age_days: 180` + manual re-download when new edition detected. |

##### Assumption 3: "EEOC needs a separate pipeline from Tier 4 agency sources"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | EEOC uses the exact same Playwright crawler as DIR/EDD/CalHR (via `_run_crawler`). Same extraction method, same chunking strategy (`heading_based`), same storage path. The only differences are: content_category (`federal_guidance`), update frequency (quarterly vs weekly), and legal authority tier (persuasive vs informational). These are configuration differences, not pipeline differences. |
| **Product Manager** | From an implementation perspective, EEOC is architecturally identical to a Tier 4 agency source. It's in Tier 3 purely because of its legal authority classification (Skidmore deference). The refresh pipeline doesn't care about legal authority — it cares about extraction method. |
| **Resolution** | **EEOC uses the Tier 4 crawl infrastructure with Tier 3 scheduling.** `max_age_days: 90` (quarterly). `--tier persuasive` filter captures it based on content_category=`federal_guidance`. No new pipeline code needed — configuration only. |

##### Assumption 4: "EEOC guidance should be ingested despite political volatility"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | EEOC guidance is politically dependent — guidance rescissions happen across administrations. Stale or rescinded EEOC content could be actively misleading to attorneys. Quarterly refresh is important to catch rescissions. |
| **Product Manager** | The ROI depends on query volume involving federal employment law. For California-focused platform, most queries are state law. EEOC adds value for Title VII, ADA, GINA coverage that overlaps with FEHA. The config already exists and is enabled — marginal effort to include in refresh. |
| **Resolution** | **Ingest EEOC in T3.** Config already exists. Crawl pipeline works. Marginal effort. But note: quarterly refresh is mandatory to catch guidance rescissions. Add a warning in `source-health` if EEOC is >90 days stale. |

---

#### Phase T3-A: Configuration & Static Source Handling

> **Goal**: Tier 3 sources have staleness thresholds, static sources have corpus confirmation, EEOC works through the crawl pipeline.
>
> **Why this is one phase**: Two sources are static (minimal work) and one uses existing crawl infrastructure (configuration only). Total new code is small — the `static` flag and corpus confirmation logic.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T3-A.1 | **Add refresh config to Tier 3 source YAMLs** | Add `refresh.max_age_days` to `dlse_opinions.yaml` (365 — annual confirmation), `dlse_manual.yaml` (180 — semi-annual), `eeoc.yaml` (90 — quarterly). Add `refresh.static: true` to `dlse_opinions.yaml`. Add `refresh.cron_hint` documentation. | T1-A.2 |
| T3-A.2 | **Implement corpus confirmation for static sources** | Add `static` flag support to `RefreshConfig`. When `refresh.static: true` in a source YAML, the `refresh` command skips full extraction and performs: (a) HTTP HEAD to source base_url to verify accessibility, (b) query stored document count for this source, (c) report "corpus confirmed (N docs)" or "source unreachable." If document count somehow changed (manual re-ingest happened), update `last_refreshed_at`. | T1-B |
| T3-A.3 | **Add DLSE Manual to `--check-updates`** | Extend `source-health --check-updates` (from T2-B.2) to include DLSE Manual PDF URL. Reports "new edition available" or "current edition" based on HTTP HEAD Content-Length/Last-Modified comparison against stored `.dlse_manual_meta.json`. | T2-B.2 |
| T3-A.4 | **Add `persuasive` to `--tier` filter** | Verify `--tier persuasive` captures DLSE opinions, DLSE manual, and EEOC based on content_category values (`opinion_letter`, `enforcement_manual`, `federal_guidance`). | T1-B.6 |
| T3-A.5 | **Ingest and validate EEOC through crawl pipeline** | Run `refresh --source eeoc --auto-embed`. Note: EEOC may not be ingested yet — first run is initial ingest, not refresh. Verify: Playwright crawl completes with 3.0s rate limit, content_category=`federal_guidance`, change report shows new documents, `source-health` shows FRESH. Second run should show 0 changes (content_hash dedup). | T3-A.1, T1-B |
| T3-A.6 | **[GATE]** `refresh --all --tier persuasive --auto-embed --if-stale` handles all 3 sources: DLSE opinions confirmed (static), DLSE manual checked for updates, EEOC crawled. Change reports and `source-health` accurate for all. | T3-A.1–T3-A.5 |

**Tests**: Static corpus confirmation (mock HEAD success/failure, document count match/mismatch). DLSE manual update detection (mock HEAD with changed Content-Length). EEOC crawl through refresh pipeline (mock crawl results). `--tier persuasive` filter. ~10 tests.

**Framework contribution**: The `refresh.static: true` flag is shared infrastructure — any future closed corpus (e.g., historical case law archives) can use the same confirmation mechanism.

---

#### Tier 3 Summary — **IMPLEMENTED**

| Phase | Focus | Tests | Key Deliverable | Status |
|-------|-------|-------|-----------------|--------|
| **T3-A** | Config + static sources + EEOC | 18 | Corpus confirmation, DLSE update detection, EEOC validation | DONE |
| **Total** | | **18** | Automated persuasive authority refresh pipeline | |

---

### Tier 4: Agency Guidance & Educational — Refresh Pipeline

**Sources**: DIR/DLSE, EDD, CalHR, CRD, Legal Aid at Work
**Extraction method**: All 5 use Playwright crawler (`_run_crawler`)
**3 already ingested** (DIR, EDD, CalHR). **2 need initial ingest** (CRD, Legal Aid at Work).

#### Pressure Test: Assumptions Examined

##### Assumption 1: "All 5 agency sources need weekly refresh"

| Lens | Challenge |
|------|-----------|
| **Business Analyst** | CalHR updates quarterly at most (bargaining contract cycles). EDD updates are event-driven (January 1 benefit changes). Legal Aid at Work updates monthly (critical window: January 1 new laws). DIR and CRD are the most dynamic — weekly is appropriate. A uniform weekly cadence wastes Playwright rendering time on stable sources. |
| **Technical Architect** | With `--if-stale`, weekly cron is a no-op for fresh sources. Per-source `max_age_days` prevents redundant crawls. The cost of a no-op check is negligible (freshness is a DB query, not an HTTP request). |
| **Resolution** | **Per-source `max_age_days`**: DIR (7), CRD (7), EDD (14), Legal Aid at Work (14), CalHR (30). Weekly cron checks all; only stale sources re-crawl. |

##### Assumption 2: "We need crawl resume capability for long Playwright crawls"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | A 300-page Playwright crawl takes ~10 minutes at 2.0s rate limit. If it fails at page 200, we re-render 200 already-stored pages on retry. But `upsert_document()` content_hash dedup means the DB impact is zero — the pages are unchanged. The cost is only Playwright rendering time (~7 minutes wasted). |
| **Software Architect** | Resume capability requires: tracking visited URLs, persisting crawl state, resuming from checkpoint. This is significant complexity (new table or file, state management, edge cases around partial pages) for a ~7 minute savings on failure. With `--if-stale` + weekly cron, a failed crawl just retries next week. The knowledge base is at most 1 week stale for that source. |
| **Product Manager** | For a single-operator system with weekly cadence, a 1-week staleness window on crawl failure is acceptable. The operator can also manually re-run `refresh --source dir`. |
| **Resolution** | **Don't build crawl resume.** Re-crawls are cheap due to content_hash dedup. Failed crawls retry next week. Accept the ~10 minute penalty on failure. If crawl failure rate exceeds 20%, revisit. |

##### Assumption 3: "DIR's 10% error rate needs a dedicated fix"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | 30 of 300 URLs failed during the last crawl. Before building retry/recovery infrastructure, diagnose the root cause. Failure modes could be: dead links (remove from allowlist), Playwright timeouts (increase timeout), rate limiting (increase delay), or selector changes (update selectors). Each has a different fix. Don't build generic infrastructure for a specific problem. |
| **Resolution** | **Investigation task first.** Analyze the 30 failed URLs, categorize failure modes, fix based on findings. This is a debugging task, not an architecture task. |

##### Assumption 4: "CalHR's oversized chunk (37,820 tokens) needs a chunker fix"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | The heading-based chunker (`chunk_document()` in `chunker.py`) already has `_split_large_section()` which enforces `max_tokens` by splitting at paragraph boundaries, with sentence-level fallback for oversized paragraphs. If the chunker already enforces max_tokens, the 37,820-token chunk likely predates the enforcement or represents a bug in the splitting logic. |
| **Software Architect** | Before building a fix, verify: (1) does re-ingesting CalHR with the current chunker produce the same oversized chunk? If not, it's stale data — just re-ingest. If yes, there's a genuine bug in `_split_large_section()` that needs investigation. |
| **Resolution** | **Verify before fixing.** Re-run `refresh --source calhr --auto-embed` with the current chunker. If the oversized chunk disappears, the fix is just a re-ingest. If it persists, investigate `_split_large_section()` for edge cases (e.g., very long lines without paragraph breaks). |

##### Assumption 5: "CRD and Legal Aid at Work need to be ingested before they can be refreshed"

| Lens | Challenge |
|------|-----------|
| **Technical Architect** | The refresh pipeline handles first-run ingestion correctly — `upsert_document()` treats all documents as `NEW` on first run. No special handling needed. `refresh --source crd` works identically whether the source has 0 or 300 existing documents. |
| **Resolution** | **No special ingestion step.** First `refresh` run IS the initial ingest. The change report will show all documents as NEW, which is correct. |

##### Assumption 6: "D4 (CrawlConfig decoupling) should happen in T4"

| Lens | Challenge |
|------|-----------|
| **Software Architect** | D4 is about non-crawl sources creating dummy CrawlConfigs with `"https://placeholder.invalid"`. Agency sources legitimately USE CrawlConfig via `to_crawl_config()`. D4 doesn't benefit T4 at all — it benefits statutory/caselaw/DLSE sources that create the dummy. |
| **Resolution** | **D4 is not a T4 task.** Updated in the debt ledger: trigger is "next modification to Pipeline.__init__ for non-crawl sources." |

---

#### Phase T4-A: Configuration & Existing Source Validation

> **Goal**: DIR, EDD, and CalHR (already ingested) work through the unified refresh pipeline.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T4-A.1 | **Add refresh config to Tier 4 source YAMLs** | Add `refresh.max_age_days` to: `dir.yaml` (7), `edd.yaml` (14), `calhr.yaml` (30), `crd.yaml` (7), `legal_aid_at_work.yaml` (14). Add `refresh.cron_hint` documentation. | T1-A.2 |
| T4-A.2 | **Add `agency` to `--tier` filter** | Verify `--tier agency` captures all 5 agency sources based on content_category values (`agency_guidance`, `legal_aid_resource`). Ensure EEOC (`federal_guidance`) is NOT captured by `--tier agency` — it belongs to `--tier persuasive`. | T1-B.6 |
| T4-A.3 | **Validate DIR refresh through unified pipeline** | Run `refresh --source dir --auto-embed`. Verify: Playwright crawl completes, change report shows accurate counts, `source-health` shows FRESH, per-URL errors are isolated (don't abort the crawl). Note error count for comparison with T4-B.1. | T4-A.1, T1-B |
| T4-A.4 | **Validate EDD and CalHR refresh** | Run `refresh --source edd --auto-embed` and `refresh --source calhr --auto-embed`. Verify same criteria as T4-A.3. For CalHR, check whether the 37,820-token chunk still exists after re-ingest with current chunker (see Assumption 4). | T4-A.1, T1-B |
| T4-A.5 | **[GATE]** DIR, EDD, and CalHR all refresh through the unified pipeline. Change reports accurate. `source-health` shows FRESH. CalHR oversized chunk status determined (stale data or genuine bug). | T4-A.1–T4-A.4 |

**Tests**: Tier filter captures correct sources (excludes EEOC). Playwright crawl through refresh pipeline (mock crawl results). Per-source `max_age_days` respected by `--if-stale`. ~7 tests.

---

#### Phase T4-B: New Source Ingestion & Crawl Reliability

> **Goal**: CRD and Legal Aid at Work are ingested. DIR error rate is investigated and resolved. CalHR oversized chunk resolved.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T4-B.1 | **Investigate DIR 10% crawl error rate** | Analyze the 30 failed URLs from the last DIR crawl (available in `crawl_runs` summary or structlog output). Categorize failure modes: dead links, Playwright timeouts, HTTP errors, selector failures, rate limiting. Propose fix based on findings. Document results. This is investigation, not coding — 1-2 hours. | — |
| T4-B.2 | **Fix DIR crawl errors based on investigation** | Implement fix from T4-B.1. Options: update blocklist to exclude dead URLs, increase Playwright timeout, adjust rate limit, update content selector. Re-run DIR crawl. Target: <3% error rate (9 or fewer failures). | T4-B.1 |
| T4-B.3 | **Resolve CalHR oversized chunk** | Based on T4-A.4 findings: (a) If the oversized chunk disappeared on re-ingest with current chunker, verify and close — no code change needed. (b) If it persists, investigate `_split_large_section()` in `chunker.py` for edge cases (e.g., content without paragraph breaks, very long single-line content). Fix the edge case and verify CalHR re-ingest produces no chunks exceeding `max_tokens`. | T4-A.4, `processing/chunker.py` |
| T4-B.4 | **Ingest CRD** | Run `refresh --source crd --auto-embed`. Verify: seed URLs crawled (100 max pages), content_category=`agency_guidance`, change report shows new documents, `source-health` shows FRESH, chunks are discoverable via hybrid search. | T4-A.1, T1-B |
| T4-B.5 | **Ingest Legal Aid at Work** | Run `refresh --source legal_aid_at_work --auto-embed`. Verify: fact sheets crawled with 10.0s rate limit (polite nonprofit), content_category=`legal_aid_resource`, change report accurate, chunks discoverable via search. Note: Legal Aid fact sheets are consumer-friendly — verify they appear in consumer mode retrieval. | T4-A.1, T1-B |
| T4-B.6 | **[GATE]** DIR error rate <3%. CalHR has no oversized chunks. CRD and Legal Aid at Work are ingested, embedded, and searchable. `source-health` shows all 5 agency sources FRESH. | T4-B.1–T4-B.5 |

**Tests**: CalHR chunk bounds (no chunk exceeds `max_tokens` after re-ingest). CRD ingestion verification (document count > 0, chunks searchable). Legal Aid ingestion verification (content_category correct, consumer mode inclusion). DIR error rate assertion. ~10 tests.

---

#### Phase T4-C: All-Tier Scheduling & Final Validation

> **Goal**: All 13 refreshable sources run on schedule via GitHub Actions. Operational runbook complete.
>
> **Why this is in T4**: This phase depends on all tiers being complete. It validates the entire system end-to-end and sets up production scheduling.

| # | Task | Description | Builds On |
|---|------|-------------|-----------|
| T4-C.1 | **Extend GitHub Actions workflow for all tiers** | Update `.github/workflows/refresh.yml` (from T1-C.2) to include all tiers with appropriate cadence. Example schedule: `0 3 * * 0` (Sunday 3am — statutory weekly), `0 3 1 * *` (1st of month — regulatory), `0 3 1 */3 *` (quarterly — persuasive), `0 3 * * 1,4` (Mon/Thu — agency). All jobs use `--if-stale --auto-embed`. Playwright installation step for agency crawls. Separate job per tier for isolation (one tier's failure doesn't block others). | T1-C.2, all tiers |
| T4-C.2 | **End-to-end validation across all tiers** | Run `refresh --all --auto-embed --if-stale`. Verify all sources handled correctly: statutory refreshed, regulatory refreshed, persuasive confirmed/crawled, agency crawled. Change reports generated for all. `source-health` shows all 13 sources FRESH. `/api/refresh-status` returns complete state with per-source details. | All phases |
| T4-C.3 | **Update KNOWLEDGE.md with operational runbook** | Document: per-source refresh cadence table, GitHub Actions schedule configuration, troubleshooting guide (crawl failures, PUBINFO download failures, stale source remediation, manual re-ingest procedure), `source-health` output reference, change report JSON schema reference. | All phases |
| T4-C.4 | **[GATE]** PO approves all-tier refresh pipeline. All 13 sources refreshable via `refresh --all --auto-embed --if-stale`. GitHub Actions workflow handles scheduling per-tier. Source health dashboard shows complete coverage. Operational runbook reviewed and approved. | T4-C.1–T4-C.3 |

**Tests**: All-tier refresh integration (mock sources, verify routing). GitHub Actions workflow dry-run validation. ~5 tests.

---

#### Tier 4 Summary — IMPLEMENTED

| Phase | Focus | Tests | Key Deliverable | Status |
|-------|-------|-------|-----------------|--------|
| **T4-A** | Enrich crawl_runs.summary | 1 | Change metrics (new/updated/unchanged/deactivated) in summary JSON | DONE |
| **T4-B** | Validate --tier agency filter | 5 | Agency tier filter + config validation | DONE |
| **T4-C** | DIR errors + CalHR chunk | 2 | DIR root cause analysis, chunker final-flush cascade fix | DONE |
| **T4-D** | Health dashboard CLI + API | 8 | `dashboard` CLI + `/api/dashboard` endpoint, grouped by tier | DONE |
| **T4-E** | GitHub Actions all-tier + validation | 9 | Per-tier cron jobs, Playwright for agency, health-check job, all-tier integration tests | DONE |
| **Total** | | **25** | Complete agency refresh + health dashboard + CI scheduling | |

**Key deliverables:**
- **Enriched summaries**: `new_documents`, `updated_documents`, `unchanged_documents`, `deactivated_sections` persisted in `crawl_runs.summary` JSON for all 3 pipeline types (statutory, caselaw, crawler)
- **CalHR chunker fix**: `_split_large_section()` final flush cascades to `_split_by_sentences()` when accumulated text exceeds `max_tokens`
- **Health dashboard**: `employee-help dashboard [--json]` CLI command + `GET /api/dashboard` endpoint. Shows docs/chunks/age/status/errors/method per source, grouped by tier, with summary footer
- **GitHub Actions**: 5 per-tier jobs (statutory weekly, regulatory monthly, persuasive quarterly, agency Mon/Thu, caselaw bimonthly) + post-refresh health-check job. Agency job installs Playwright. Each tier isolated (one failure doesn't block others)
- **DIR investigation**: 10% error rate from Playwright timeouts, broken links, no retry. Crawler-level fix deferred — documented for future work

---

### Cross-Tier Summary — ALL TIERS COMPLETE

| Tier | Sources | Tests | Key Insight | Status |
|------|---------|-------|-------------|--------|
| **T1** | 9 statutory + CourtListener | 48 | Builds the entire framework. Heaviest tier. | DONE |
| **T2** | 3 regulatory (CCR × 2, CACI) | 17 | Mostly configuration. Framework does the work. | DONE |
| **T3** | 3 persuasive (DLSE × 2, EEOC) | 18 | Two static sources + one crawl. Lightweight. | DONE |
| **T4** | 5 agency + dashboard + CI | 25 | Completes the system. Dashboard + all-tier scheduling. | DONE |
| **Grand Total** | **21 sources** | **108** | Framework built once in T1; reused across all tiers. | **COMPLETE** |

Note: 21st source (CourtListener) is Tier 1 with `caselaw` filter support and `max_age_days: 30`.

### Cross-Tier Dependencies & Sequencing (ALL COMPLETE)

```
T1 (framework) ──→ T2 (regulatory)    ─┐
                ├──→ T3 (persuasive)   ├──→ T4-E (all-tier scheduling + final validation) ✓
                └──→ T4-A/B/C/D (agency + dashboard) ─┘
```

T2, T3, and T4-A/B can be developed **in parallel** after T1 completes. T4-C (final validation + all-tier scheduling) depends on all tiers completing — it is the capstone phase.

### Cross-Tier Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Cornell LII goes offline** | Medium | CCR sources have local cache in `data/ccr/`. Stale but not broken. Long-term: consider migrating to official OAL source. |
| **EEOC guidance rescinded mid-cycle** | Medium | Quarterly refresh + `source-health` warning if >90 days stale. Consider monitoring EEOC newsroom RSS for guidance changes. |
| **Playwright breaks on site redesign** | Medium | Content selectors (`#main-content`, `#et-main-area`, `.main-primary`, `main`) are site-specific. A redesign requires selector update. `source-health` would show failures on next crawl. Per-source error isolation prevents cascading failures. |
| **Legal Aid at Work 10s rate limit slows crawl** | Low | 150 pages × 10s = 25 minutes. Acceptable for monthly cadence. Cannot reduce — polite rate limit for nonprofit. |
| **DIR error rate persists after fix** | Low | If errors are inherent (dead gov links, dynamic content), update blocklist to exclude unfixable URLs and accept a lower page count. |
| **GitHub Actions Playwright setup fails** | Low | Playwright requires Chromium download in CI. Use `npx playwright install chromium` in workflow. Pin Playwright version. Test in CI before relying on it. |

### Operational Runbook

#### Refresh Cadence (GitHub Actions)

| Tier | Cron | Schedule | Timeout | Notes |
|------|------|----------|---------|-------|
| Statutory | `0 3 * * 0` | Sunday 3am UTC | 30min | Downloads PUBINFO first |
| Agency | `0 3 * * 1,4` | Mon/Thu 3am UTC | 180min | Installs Playwright + Chromium |
| Regulatory | `0 3 1 * *` | 1st of month 3am | 30min | CCR + CACI |
| Persuasive | `0 3 1 1,4,7,10 *` | Quarterly | 30min | Static confirmation for DLSE |
| Case Law | `0 4 1,15 * *` | 1st & 15th 4am | 60min | CourtListener API |

#### Manual Operations

```bash
# Check health of all sources
employee-help dashboard
employee-help dashboard --json   # Machine-readable
employee-help source-health      # Legacy table view

# Manual refresh (single source)
employee-help refresh --source labor_code --auto-embed

# Manual refresh (entire tier)
employee-help refresh --all --tier statutory --auto-embed

# Force refresh (ignore staleness)
employee-help refresh --all --auto-embed  # no --if-stale

# GitHub Actions manual trigger
gh workflow run refresh.yml -f tier=agency -f force=true
```

#### Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Source shows STALE | `last_refreshed_at` older than `max_age_days` | Run `refresh --source <slug> --auto-embed` |
| Source shows NEVER_RUN | No crawl_runs for this source | First-time ingest: `refresh --source <slug> --auto-embed` |
| Agency crawl has errors | Playwright timeouts, dead links | Check `crawl_runs.summary` for error details; update blocklist if needed |
| PUBINFO download fails | CA legislature server down / 404 | Retry with `pubinfo-download --year 2025 --force`; existing data still valid |
| CalHR oversized chunk | `_split_large_section` edge case | Fixed in chunker — re-ingest: `refresh --source calhr --auto-embed` |
| Embedding fails | OOM on torch | Reduce batch size in `config/rag.yaml`; check available RAM |

### Updated Architectural Debt Ledger

| Debt Item | Severity | Trigger | Target |
|-----------|----------|---------|--------|
| D3: Extraction method switch statement (OCP) | Soft | Adding 2+ new extraction methods OR T2 testing reveals friction | T2-C (optional) |
| D4: Dummy CrawlConfig for non-crawl sources (LSP) | Soft | Next modification to Pipeline.__init__ for non-crawl sources | Any |
| D5: Pipeline.py mixed responsibilities (CCP) | Soft | Pipeline.py exceeds ~1200 lines or changes for 3+ reasons in one sprint | Any |

These are conscious, bounded decisions with explicit payback triggers.
