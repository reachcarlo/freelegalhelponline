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
