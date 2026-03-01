# PRODUCT REQUIREMENTS 2.0 — Market-Driven Product Roadmap

> **Project:** FindLegalHelp.online — AI-Powered California Employment Law Platform
> **Author:** Claude (Opus 4.6) with Product Manager + Venture Capital lens
> **Date:** 2026-02-28
> **Status:** APPROVED — All 8 PO decisions resolved (2026-02-28)
> **Supersedes:** EXPANDED_REQUIREMENTS.md Phases 3C through 5 (Phases 1–3B are DONE and preserved)

---

## Executive Summary

Three independent market research reports converge on the same conclusion: **there is a wide-open, multi-billion-dollar gap in California employment law technology that nobody is filling**. Enterprise tools (Harvey, CoCounsel) are priced for BigLaw. Consumer tools (DoNotPay, LegalZoom) are generic and unreliable. Plaintiff-side AI tools (EvenUp, Eve Legal) serve personal injury, not employment law. No product exists that combines consumer-facing case evaluation with attorney-side workflow tools for the California employment law market.

FindLegalHelp.online sits at the exact intersection of this opportunity. We have already built:
- A curated knowledge base of 24,106 chunks from 10 authoritative California sources
- A dual-mode RAG pipeline (consumer + attorney) with verified citations
- A live web interface at findlegalhelp.online with multi-turn conversation
- 774 passing tests, automated evaluation, and production deployment

**The pivot**: Move from a passive research tool to an **interactive platform that (1) helps workers assess their claims, (2) connects them with employment attorneys, and (3) gives those attorneys AI-powered workflow tools**. The consumer side is the free acquisition engine. The attorney side is the revenue engine. The data flywheel from case flow is the moat.

**Build philosophy**: We are in build mode. The market research validates the pain points. Rather than gate features behind extensive market validation, we build the things that clearly solve documented problems using free, public-domain data sources. Proprietary technology and IP accumulation over vendor dependency. If it solves a real pain point, they will come.

---

## Part 1: What We Have Today (Completed)

These phases are DONE and form the foundation for everything that follows.

| Phase | Status | What It Delivered |
|-------|--------|-------------------|
| Phase 1 | COMPLETE | CRD crawler, content extraction, SQLite storage |
| Phase 1.5 | COMPLETE | 10 sources (6 statutory + 3 agency + CACI), 24,106 chunks, source registry |
| Phase 2 | COMPLETE | RAG pipeline (bge-base embeddings, LanceDB, hybrid search, Claude generation, citation validation) |
| Phase 3B | COMPLETE | MVP web app (Next.js + FastAPI), SSE streaming, multi-turn conversation, analytics, feedback, SEO topic pages, polished UX |

**Current metrics:**
- Knowledge base: 20,871 documents, 24,106 active chunks, 10 sources
- Search quality: Consumer P@5 0.888, Attorney P@5 0.808, Citation top-1 1.000
- Per-query cost: Consumer $0.006, Attorney $0.032
- Tests: 774 passing
- Live at: findlegalhelp.online (Railway + Vercel)

---

## Part 2: Market Analysis Summary

### The Gap

| Market Segment | Current Tools | Price | Employment Law Coverage |
|----------------|--------------|-------|----------------------|
| Enterprise (BigLaw) | Harvey AI, CoCounsel | $225–500/user/mo | Mentioned but not specialized |
| Small Firms | Clio, ChatGPT | $39–159/user/mo | None — generic AI add-ons |
| Plaintiff (PI) | EvenUp, Eve Legal | Per-case/enterprise | Personal injury only |
| Consumer | DoNotPay, LegalZoom | $15–99/mo | Generic; DoNotPay fined $193K by FTC |
| **CA Employment** | **Nobody** | **N/A** | **This is the gap** |

### The Numbers

- **85%** of California civil legal problems receive inadequate or no legal help
- **$2 billion** annual wage theft in California
- **30,000+** CRD intakes per year, **10,000+** PAGA filings, **5,000+** employment class actions
- **8,500–13,600** California attorneys practice employment law; **1,400+** CELA members
- Employment lawyers pay **$100–800 per qualified lead**
- Average employment case settlement: **$20,000–$300,000** (contingency fee: 33–40%)
- Solo practitioner tech budget: **< $3,000/year** — CoCounsel costs more for 2 months
- Stanford study: Westlaw AI hallucinates **33%** of the time; Lexis+ AI **17%**

### The Thesis

> **No one has built the EvenUp of employment law.** EvenUp proved a $2B+ company can be built by going deep into a single practice area with niche-specific AI. The two-sided marketplace — consumer case evaluation as the free wedge, attorney workflow tools as the paid product — is a completely open field.

### Competitive Moat (Zero to One Analysis)

The moat is NOT a fine-tuned model (models commoditize quickly). The defensible assets are:

1. **The curated California employment law knowledge base** — structured, linked, kept current through automated pipelines. Hard to build, harder to maintain.
2. **The citation verification pipeline** — engineering to ensure every citation is real, current, and relevant. Integration of Eyecite, CourtListener, statute currency checking.
3. **Practice-area-specific workflows** — intake screening, demand letter templates, discovery request generators, deadline calculators. These embed deep domain knowledge.
4. **Network effects from user data** — research patterns, citation preferences, case outcome data. More users = better product.

---

## Part 3: The Free Legal Data Pipeline

A critical design principle: **build on free, public-domain data sources to maximize IP and minimize dependency.** The data is free. The engineering to structure, link, verify, and keep it current is the defensible asset.

### 3.1 Data Sources — Current (Operational)

| Source | Type | Access Method | Status |
|--------|------|---------------|--------|
| California Labor Code | Statute | PUBINFO database (leginfo FTP) | INGESTED |
| Government Code (FEHA) | Statute | PUBINFO database | INGESTED |
| Government Code (Whistleblower) | Statute | PUBINFO database | INGESTED |
| Unemployment Insurance Code | Statute | PUBINFO database | INGESTED |
| Business & Professions Code | Statute | PUBINFO database | INGESTED |
| Code of Civil Procedure | Statute | PUBINFO database | INGESTED |
| CACI Jury Instructions | Instructions | courts.ca.gov PDF | INGESTED |
| DIR/DLSE | Agency guidance | Playwright crawler | INGESTED |
| EDD | Agency guidance | Playwright crawler | INGESTED |
| CalHR | Agency guidance | Playwright crawler | INGESTED |
| CRD | Agency guidance | Playwright crawler | INGESTED |

### 3.2 Data Sources — Next Priority (Free, Public Domain)

| Source | Type | Access Method | Value | Build Effort |
|--------|------|---------------|-------|-------------|
| **CourtListener** (Free Law Project) | Case law | Free REST API + bulk data (AWS S3) | 9M+ decisions, CA Supreme Court + Courts of Appeal. Citation verification via API. Webhook alerts for new cases. **Foundation for case law layer.** | Medium |
| **Harvard Caselaw Access Project** | Historical case law | HuggingFace (CC0 license) | 6.7M cases through 2018. Bulk download. Supplements CourtListener for historical depth. | Medium |
| **Eyecite** (Free Law Project) | Citation extraction | Python library (open source) | Extracts citations from any legal text. Critical for citation verification pipeline. | Low |
| **California Code of Regulations (CCR)** | Regulations | Westlaw-free via CA OAL website | Title 2 (Fair Employment), Title 8 (Industrial Relations). Administrative rules implementing statutes. | Medium |
| **DLSE Opinion Letters** | Interpretive authority | dir.ca.gov PDFs | Courts give "great weight" to DLSE interpretations. PDF extraction via pdfplumber. | Medium |
| **DLSE Enforcement Manual** | Interpretive authority | dir.ca.gov PDF | Comprehensive Labor Code interpretations. Single large PDF. | Low |
| **IWC Wage Orders** | Regulations | dir.ca.gov PDFs | 17 industry-specific wage orders. PDFs codified in CCR Title 8. | Low |
| **Legal Aid at Work fact sheets** | Consumer guidance | legalaidatwork.org (HTML) | 100+ fact sheets, multilingual, highly practical. | Low |
| **CA Courts Self-Help** | Consumer guidance | selfhelp.courts.ca.gov | Employment-specific guidance, filing procedures. | Low |
| **EEOC guidance** | Federal guidance | eeoc.gov (HTML) | Federal employment discrimination law (supplements FEHA). | Low |
| **Justia** | Case law (secondary) | justia.com | California appellate opinions, searchable. Free access. | Low |
| **LegiScan** | Legislative tracking | API (free tier) | Near-real-time legislative change tracking. JSON/XML/CSV exports. | Low |
| **Google Scholar** | Case law verification | Scholar search | "How Cited" feature approximates Shepardizing. | Low |

### 3.3 Data Pipeline Architecture (Target State)

```
                    ┌─────────────────────────────────────────┐
                    │          INGESTION LAYER                 │
                    │                                         │
 PUBINFO (statutes) ──┐  CourtListener API ──┐               │
 Courts.ca.gov PDFs ──┤  Harvard CAP bulk  ──┤               │
 Agency crawlers    ──┤  DLSE PDFs         ──┤  Extractors   │
 Legal Aid sheets   ──┤  CCR/Wage Orders   ──┤  + Loaders    │
 EEOC guidance      ──┘  LegiScan API      ──┘               │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │          PROCESSING LAYER                │
                    │                                         │
                    │  Text extraction (pdfplumber, BS4)      │
                    │  Citation extraction (Eyecite)          │
                    │  Structure-aware chunking               │
                    │  Content categorization                 │
                    │  Citation linking (statute ↔ case)      │
                    │  Embedding (bge-base-en-v1.5)           │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │          KNOWLEDGE LAYER                 │
                    │                                         │
                    │  SQLite (documents, chunks, metadata)   │
                    │  LanceDB (vectors, hybrid search)       │
                    │  Citation graph (statute → case links)  │
                    │  Currency tracking (amended/repealed)   │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │          APPLICATION LAYER               │
                    │                                         │
                    │  Consumer: Rights assessment, guidance  │
                    │  Attorney: Research, drafting, workflow  │
                    │  Marketplace: Lead routing (future)     │
                    │  API: Embeddable for HR platforms       │
                    └─────────────────────────────────────────┘
```

---

## Part 4: Legal & Compliance Guardrails

> **This section is non-negotiable.** The product owner's license and the legality of the product depend on getting this right.

### 4.1 The Bright Line: Legal Information vs. Legal Advice

| The product CAN do | The product CANNOT do |
|---|---|
| Provide general information about California employment laws | Apply legal analysis to a specific user's facts and recommend a course of action |
| Explain procedures, deadlines, and available remedies in general terms | Tell someone "you have a strong discrimination case" |
| Offer self-help tools like blank forms and calculators | Generate final legal documents without attorney review |
| Show comparable case outcomes without predicting specific results | Market the AI as equivalent to a licensed attorney |
| Generate document DRAFTS that require attorney review before use | Provide case-specific legal conclusions |

**Applicable law:** California Business & Professions Code sections 6125–6126 (unauthorized practice of law is a misdemeanor). The distinction between permissible "legal information" and prohibited "legal advice" is determined case by case with no bright-line rule.

### 4.2 Structural Safeguards (Must-Haves)

| Safeguard | Implementation | Status |
|-----------|---------------|--------|
| **Disclaimer on every interaction** | System prompt enforces; UI renders permanently visible banner | IMPLEMENTED (96.7% compliance in eval) |
| **"This is not legal advice" language** | Every answer, every page, consent modal on first visit | IMPLEMENTED |
| **AI nature disclosure** | California Bot Disclosure Act + SB 243 (effective Jan 2026): must disclose AI nature | IMPLEMENTED (consent modal) |
| **No attorney-client privilege** | Users must understand communications are NOT privileged | IMPLEMENTED (terms page) |
| **CCPA/CPRA compliance** | Privacy notice, right to know/delete/opt-out for collected data | PARTIAL — needs privacy policy page |
| **Attorney review of disclaimers** | PO (licensed attorney) must review and approve all disclaimer language | **[PO DECISION REQUIRED]** |
| **Document drafts marked as DRAFT** | Any generated documents clearly labeled "DRAFT — Requires Attorney Review" | NOT YET NEEDED (no document generation yet) |
| **No outcome predictions** | System must never predict case outcome or settlement value to consumers | ENFORCED via system prompt |

### 4.3 The Lead Generation / Referral Question

> **[PO DECISION REQUIRED — HIGH PRIORITY]**

The market research identifies a critical legal structure question for the attorney marketplace:

**Option A: Flat-fee advertising/marketing model**
- Charge attorneys flat advertising/marketing fees (not tied to case outcomes)
- Avoid classification as a "referral service" under B&P Code section 6155
- Simpler to operate; no State Bar certification required
- Revenue: $150–500/qualified lead (flat fee)

**Option B: Certified Lawyer Referral Service (LRS)**
- Certify under B&P Code sections 6155–6159
- Can collect "usual charges" (14–20% of attorney fees per successful referral)
- Requirements: State Bar certification ($1K–10K fee), E&O insurance ($100K/$300K minimum), $25K surety bond, two-year certification periods
- Revenue: potentially much higher per case (14–20% of $8K–$120K in fees = $1,120–$24,000 per case)
- *Jackson v. LegalMatch* (2019): connecting clients with attorneys IS a referral subject to section 6155

**Option C: Build tools only, no marketplace (defer the question)**
- Build consumer tools and attorney tools independently
- No lead routing or attorney matching
- Simplest legally; can add marketplace later
- Revenue: attorney subscriptions only ($49–149/month)

**PO-1 resolved:** Start with **Option C** (build tools, no marketplace) for the immediate build phase. **Flat-fee advertising (Option A) is the intended future direction** once consumer traffic justifies it. Architect the consumer assessment to capture structured data that could fuel lead routing later, without building routing now. Pursue Option B (certified LRS) only if revenue projections justify the setup costs.

### 4.4 Additional Compliance Items

| Requirement | Notes |
|-------------|-------|
| **California State Bar AI guidance** (Nov 2023, updated May 2025) | Lawyers using AI must understand capabilities/limitations, verify outputs, protect confidentiality, reflect efficiencies in billing |
| **ABA Formal Opinion 512** (July 2024) | Lawyers must maintain competence with AI, ensure confidentiality, verify all outputs |
| **LDA registration** | If preparing documents at client direction, may need CA Legal Document Assistant registration ($25K surety bond). Applies to consumer document generation. |

---

## Part 5: Product Roadmap — Build Phase

The roadmap is organized as **independent workstreams** that can be built in parallel with minimal dependencies. Each workstream solves a specific, documented pain point. Features are buildable with free/low-cost data sources and our existing tech stack.

### Design Principles

1. **Build on public domain data** — No proprietary data dependencies. CourtListener, PUBINFO, Harvard CAP, DLSE, CCR are all free.
2. **Zero tolerance for hallucination** — Every citation verified. Every statute checked for currency. Confidence scoring on all outputs.
3. **Prominent disclaimers** — Legal information, not legal advice. Always.
4. **Maximize IP** — Build our own extractors, parsers, verification pipelines. The engineering is the moat.
5. **Independent workstreams** — Features should not block each other. Ship as completed.
6. **Attorney workflow focus** — The market research is clear: the highest-value features save attorneys time on tasks they already do (intake screening, demand letter drafting, research, deadline tracking).

---

### Workstream A: Case Law Knowledge Base (Foundation for Everything)

**Pain point:** Attorneys spend 23% of work hours on legal research, relying on $225–500/month tools. Small firms (87% of all US law firms) use free tools like Google Scholar and ChatGPT (57% of solo attorneys). Our RAG currently has statutes and agency guidance but NO case law — the backbone of legal analysis.

**Why it matters:** Case law is what makes statutory analysis actionable. A statute says what the law is; cases say how courts interpret and apply it. Without case law, our attorney mode is incomplete. With case law, we become a genuine Westlaw alternative for the employment law vertical.

**Data sources:** All free, all public domain.

| # | Task | Source | Deliverable | Effort |
|---|------|--------|-------------|--------|
| A.1 | **CourtListener integration** — Build a loader for the CourtListener REST API. Bulk-download California Supreme Court and Courts of Appeal opinions that cite employment statutes (FEHA, Labor Code, PAGA). Filter to employment-relevant opinions using citation analysis. | CourtListener API (free, auth token) | `src/employee_help/scraper/extractors/courtlistener.py`, API client, opinion loader | Medium |
| A.2 | **Case law chunking strategy** — Design employment-case-aware chunking: opinion metadata (parties, court, date, citation), holdings/key passages, cited statutes. Each chunk carries case citation metadata (e.g., "Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028"). | A.1 | Enhanced chunker with `case_law` strategy | Medium |
| A.3 | **Eyecite citation extraction** — Integrate the Eyecite library to extract all statutory and case citations from opinion text. Build a citation linking table: case → statutes cited, statute → cases citing it. | Eyecite (open source, Free Law Project) | `src/employee_help/processing/citation_extractor.py`, citation link table in SQLite | Medium |
| A.4 | **Harvard CAP historical backfill** — Download California employment cases from the Harvard Caselaw Access Project (CC0 license on HuggingFace). Supplement CourtListener for pre-2018 coverage. | Harvard CAP (HuggingFace, CC0) | Historical case coverage | Low–Medium |
| A.5 | **Embed and index case law** — Run embedding pipeline on case law chunks. Update LanceDB with new `case_law` content category. Add `case_law` to attorney mode retrieval. | A.1–A.4 | Case law in vector store, retrievable | Low |
| A.6 | **Citation verification pipeline** — For every citation the LLM generates: (1) extract via Eyecite, (2) verify case exists via CourtListener API, (3) check statute currency against PUBINFO, (4) assign confidence score. Flag unverified citations. | CourtListener API, Eyecite, PUBINFO | `src/employee_help/generation/citation_verifier.py` | Medium |

**Target:** 2,000–5,000 California state appellate employment law opinions in the knowledge base. Every citation in LLM output verified against real sources.

**New content category:** `case_law` — included in attorney mode, excluded from consumer mode (consumers get plain-language guidance, not case citations).

**PO-3 resolved:** CA state appellate only (Supreme Court + Courts of Appeal). Federal courts (Ninth Circuit, CA district courts) revisited based on attorney feedback. Pipeline built extensible — court list and statute list are configurable, so adding federal is a config change.

---

### Workstream B: Statute Currency & Legislative Tracking

**Pain point:** California employment law changes every January 1. Attorneys spend significant time tracking annual updates. The market research calls this "the annual update problem" — solving it alone is worth a subscription. 25% of legal malpractice claims relate to missed deadlines; stale law is a close cousin.

**Data sources:** PUBINFO weekly archives (already integrated) + LegiScan API (free tier).

| # | Task | Source | Deliverable | Effort |
|---|------|--------|-------------|--------|
| B.1 | **Automated weekly refresh** — Scheduled re-download of PUBINFO full archive. Diff against current DB: detect amended, added, and repealed sections. Re-embed changed chunks. Generate change report. | PUBINFO (leginfo FTP) | `employee-help refresh --auto` with change detection | Medium |
| B.2 | **"What's New" digest** — Auto-generated summary of statutory changes for a given period. Grouped by practice area (wages, discrimination, leave, retaliation). Publishable as a blog post or email newsletter. | B.1 | `employee-help whats-new --since 2026-01-01` CLI command, markdown output | Low |
| B.3 | **Statute currency indicator** — When the LLM cites a statute, check if it has been amended since ingestion. Display a warning badge: "This section was amended effective [date]." | B.1, PUBINFO | Currency badge in citation display | Low |
| B.4 | **LegiScan integration** (optional) — Monitor pending California employment legislation in real-time. Surface "pending bill" alerts when a cited statute has active amendment proposals. | LegiScan API (free tier: 200 req/day) | `src/employee_help/scraper/extractors/legiscan.py` | Low |

**Outcome:** The knowledge base is never stale. Attorneys trust it because it tells them when something has changed. "What's new in California employment law for 2027?" becomes a killer feature every January.

---

### Workstream C: Interactive Rights Assessment (Consumer Wedge)

**Pain point:** 85% of Californians with civil legal problems receive inadequate or no help. The #1 barrier is knowledge — 24% don't know they have a legal issue, 13% of violation victims don't realize the conduct was unlawful. Workers Google "wrongful termination California" and get scattered, confusing results. No tool walks them through a structured assessment.

**Why it matters:** This is the consumer acquisition engine. Free, high-value, SEO-optimized. Every assessment generates a potential lead for the attorney marketplace (future). The market research is unambiguous: **start with the consumer claim evaluator as the wedge**.

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| C.1 | **Guided intake questionnaire** — Multi-step conversational flow that asks plain-language questions about the worker's situation. Maps answers to California employment law categories: FEHA discrimination/harassment, wrongful termination, wage theft, retaliation, PAGA violations, CFRA/FMLA leave, misclassification. Does NOT provide legal advice — presents educational information about potentially relevant rights. | New `/assess` route (frontend) + assessment logic (backend) | Medium |
| C.2 | **Statute of limitations calculator** — Based on claim type, calculate relevant deadlines: CRD (3 years), EEOC (300 days), PAGA LWDA notice (1 year), government tort claims (6 months), Labor Code claims (varies). Display urgency warnings for approaching deadlines. | Calculator component + deadline logic | Low |
| C.3 | **Agency routing guide** — "Where to file" decision tree based on claim type: CRD vs. EEOC vs. DLSE vs. LWDA vs. court. Step-by-step filing instructions with direct links to actual filing portals (ccrs.calcivilrights.ca.gov, publicportal.eeoc.gov, DLSE wage claim forms). | Agency routing logic + guide page | Low |
| C.4 | **Incident documentation helper** — Guided form for documenting workplace incidents: date, time, location, witnesses, what happened, what was said. Structured timeline builder. Exportable as a personal record (not a legal document). Prompt: "While details are fresh, write down exactly what happened." | Incident form component, local storage or session storage | Medium |
| C.5 | **Rights summary generator** — After assessment, generate a plain-language summary: "Based on what you've described, here are the California employment rights that may be relevant to your situation..." with citations to specific statutes and agency resources. Strong disclaimer: "This is educational information, not legal advice." | Summary template using existing RAG pipeline | Low |
| C.6 | **Unpaid wages calculator** — Simple calculator: input hours worked, rate, breaks missed. Compute potential unpaid wages including overtime (daily and weekly per California law), meal/rest break premiums, waiting time penalties. Based on Labor Code sections 510, 226.7, 203. | Calculator component with wage math | Low |

**SEO play:** Each claim type becomes a landing page: "Do I Have a Wrongful Termination Case in California?", "California Wage Theft: Your Rights", "FEHA Discrimination Claims Explained." These target the exact high-intent search queries ($15–80 CPC on Google Ads) with interactive tools instead of static content.

**Disclaimers:** Every step of the assessment prominently states: "This tool provides general educational information about California employment law. It does not provide legal advice, and using this tool does not create an attorney-client relationship. For advice about your specific situation, consult a licensed attorney."

---

### Workstream D: Attorney Workflow Tools (Revenue Engine)

**Pain point:** Plaintiff employment attorneys invest months of unpaid work per case (contingency), average only 2.9 billable hours per day, and spend 40–60% of their time drafting and reviewing documents. Only 27% of solo attorneys have access to litigation support software. They cobble together ChatGPT + Westlaw + Adobe Acrobat + Google Sheets.

**Why it matters:** This is where the money is. $99–149/month per attorney, positioned below CoCounsel ($225–500) and above ChatGPT ($20). A tool that saves 5 hours/month generates $2,100 in value at $420/hour billing rate. The market research identifies specific, buildable workflow features ranked by pain-point severity.

| # | Task | Attorney Pain Point | Deliverable | Effort |
|---|------|-------------------|-------------|--------|
| D.1 | **Demand letter generator** — Template-based demand letter drafting with real California citations pulled from the knowledge base. Claim types: FEHA discrimination, FEHA harassment, FEHA retaliation, Labor Code wage theft, PAGA violations, wrongful termination. Uses case facts from structured intake form. Output: Word/PDF draft marked "DRAFT — Attorney Review Required." | Each demand letter drafted from scratch (hours of work) | Template engine + claim-type templates + citation insertion | Medium |
| D.2 | **CRD complaint draft assistant** — Guided walkthrough of CRD complaint form fields. Pre-populate from intake data. Generate narrative statement of facts section. Include relevant statutory basis (Gov. Code sections). Export as fillable form or text draft. | Filing CRD complaints is procedural but time-consuming | Complaint form guide + narrative generator | Medium |
| D.3 | **Discovery request templates** — Pre-built interrogatories, requests for production, and requests for admission tailored to California employment claim types. Customizable per case. Includes form interrogatories (DISC-001) references and special interrogatories. | Discovery is "six- to eight-fold" more expensive for small plaintiff firms | Template library + customization interface | Medium |
| D.4 | **Employment law deadline tracker** — Dashboard showing all case-relevant deadlines: CRD filing (3 years from violation), EEOC dual-filing (300 days), PAGA LWDA notice (1 year), government tort claims (6 months), discovery cutoffs, trial deadlines. Auto-calculated from case start date. | 25% of malpractice claims relate to missed deadlines | Deadline calculator + dashboard | Low |
| D.5 | **Case intake screening tool** — AI-powered pre-screening: input case facts, get structured viability assessment (claim types identified, statute of limitations status, potential damages range, relevant statutes). NOT a case outcome prediction — a research summary to help attorneys decide whether to take the case. | Firms turn away 95–99% of inquiries; screening is the #1 bottleneck | Intake form + structured analysis using RAG pipeline | Medium |
| D.6 | **Export and copy tools** — Copy citation, copy analysis section, export full answer to Word/PDF. Formatted for direct insertion into briefs, memos, demand letters. | Without easy export, the tool creates extra work | Copy/export buttons + document formatter | Low |
| D.7 | **Research session memory** — Save and resume research sessions. Tag by case. Search across saved research. Build a personal knowledge base. | Attorneys research across days/weeks per case | Session persistence + search | Medium |

**PO-4 resolved:** D.5 (intake screening) + D.1 (demand letters) first — they solve the two highest-pain-point problems. D.6 (export/copy) and D.4 (deadline tracker) ship alongside as quick wins.

**Critical constraint on document generation (D.1, D.2, D.3):** All generated documents MUST be:
- Labeled "DRAFT — Requires Attorney Review Before Use"
- Generated with real, verified California citations (not hallucinated)
- Presented as starting points that require attorney judgment, not finished products
- Potentially subject to LDA (Legal Document Assistant) registration requirements if offered directly to consumers — attorney-facing only avoids this

---

### Workstream E: Knowledge Base Expansion (Depth)

**Pain point:** Our knowledge base covers statutes and agency guidance but is missing key interpretive authorities that attorneys rely on daily: DLSE opinion letters, the DLSE Enforcement Manual, IWC Wage Orders, and CCR regulations.

| # | Task | Source | Value | Effort |
|---|------|--------|-------|--------|
| E.1 | **DLSE Opinion Letters** — Scrape/download DLSE opinion letters from dir.ca.gov. Parse PDFs with pdfplumber. Index by topic and statute section. New content category: `opinion_letter`. | dir.ca.gov (PDF) | Courts give "great weight" to DLSE interpretations. Essential for wage-and-hour analysis. | Medium |
| E.2 | **DLSE Enforcement Policies & Interpretations Manual** — Download and parse the comprehensive DLSE manual. Structure by topic/section. | dir.ca.gov (PDF) | The authoritative guide to Labor Code enforcement. | Low |
| E.3 | **IWC Wage Orders** — Parse the 17 industry-specific wage orders. Structure by order number and section. Cross-reference to implementing statutes. | dir.ca.gov (PDF), CCR Title 8 | Essential for wage-and-hour practice. Meal/rest break rules vary by wage order. | Low |
| E.4 | **CCR Title 2 (Fair Employment)** — Ingest FEHA implementing regulations from the California Code of Regulations. These define terms like "reasonable accommodation" and "undue hardship" that the statute leaves vague. | CA OAL website or Cornell LII | Fills the gap between statutory text and practical application. | Medium |
| E.5 | **CCR Title 8 (Industrial Relations)** — Ingest workplace safety, wage, and hour regulations. | CA OAL website or Cornell LII | Workplace safety and wage-and-hour regulatory detail. | Medium |
| E.6 | **Legal Aid at Work fact sheets** — Ingest 100+ multilingual fact sheets covering overtime, discrimination, leave, workplace injury. New content category: `legal_aid_resource`. | legalaidatwork.org (HTML) | Excellent consumer-mode content. Multilingual. Highly practical. | Low |
| E.7 | **EEOC guidance** — Federal employment discrimination guidance (Title VII, ADA, ADEA). Supplements FEHA coverage. | eeoc.gov (HTML) | Federal law context for California claims. | Low |

---

### Workstream F: Citation Verification & Anti-Hallucination

**Pain point:** The existential risk. 600+ documented AI hallucination cases in court filings. Stanford study: Westlaw AI hallucinates 33% of the time. One fake citation destroys all credibility with attorneys. Our current citation validation checks against our own knowledge base, but does not verify against external sources.

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| F.1 | **Eyecite integration** — Extract all citations from LLM-generated text using the Eyecite library (Free Law Project). Normalize to standard citation format. | Citation extraction module | Low |
| F.2 | **CourtListener case verification** — For every case citation: query CourtListener API to verify the case exists, check the citation format, confirm jurisdiction (California), validate date. Return confidence score. | Case citation verifier | Medium |
| F.3 | **Statute currency check** — For every statute citation: verify against PUBINFO that the section exists and is active (not repealed). Check if amended since last ingestion. | Statute currency verifier | Low |
| F.4 | **Confidence scoring** — Aggregate verification results into a per-citation confidence score: Verified (green), Unverified (yellow), Suspicious (red). Display to user. | Confidence UI badges | Low |
| F.5 | **Citation audit log** — Log every citation generated, its verification status, and the verification source. Use for ongoing quality monitoring and reporting. | Audit table in SQLite, CLI report | Low |

**Target:** Every citation presented to a user has been mechanically verified against at least one authoritative external source. Zero hallucinated citations in production.

---

### Workstream G: SEO & Content Engine

**Pain point:** Employment law keywords cost $15–80+ per click on Google Ads. Law firm websites convert at only 5–7%. Organic SEO is the only viable consumer acquisition channel at scale. Our 11 topic pages are a start, but the market research is clear: interactive tools outperform static content.

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| G.1 | **Claim-type landing pages** — One interactive page per major claim type (8 total): wrongful termination, FEHA discrimination, FEHA harassment, wage theft, retaliation, PAGA, CFRA leave, misclassification. Each includes: overview, elements, deadlines, "Do I have a case?" entry point, 5+ FAQs with schema.org markup, internal links. | 8 new SSG pages with FAQPage + LegalService schema | Medium |
| G.2 | **"What's New" blog** — Monthly automated digest of California employment law changes (from Workstream B). Publish as SSG pages. Target: "California employment law changes 2026/2027" searches. | Blog template + automated content from B.2 | Low |
| G.3 | **Calculator pages** — Standalone calculator tools (overtime calculator, unpaid wages calculator, statute of limitations calculator) as individual SEO-optimized pages. These rank well because they're interactive and useful. | Calculator pages with schema.org markup | Low |
| G.4 | **Spanish language pages** — Translate top 5 topic pages to Spanish. ~39% of CA workforce is Hispanic/Latino; ~7 million Californians speak English "less than very well." Massive underserved market. | Translated pages, hreflang tags | Low–Medium |

---

### Workstream H: Infrastructure & Quality

| # | Task | Deliverable | Effort |
|---|------|-------------|--------|
| H.1 | **CI/CD pipeline** — GitHub Actions: run tests on PR, deploy to staging on merge, production with manual approval. Rollback procedure. | `.github/workflows/` | Low |
| H.2 | **Error tracking** — Sentry integration for both backend (FastAPI) and frontend (Next.js). Alert on error spikes. | Sentry setup | Low |
| H.3 | **Structured logging** — Aggregate logs from Railway. Monitor: error rates, response times, LLM costs, daily query counts. | Log aggregation setup | Low |
| H.4 | **Privacy policy page** — CCPA/CPRA-compliant privacy policy. Document what data we collect (queries, feedback, IP addresses), how it's used, and user rights. | `/privacy` page | Low |
| H.5 | **Input sanitization** — Validate and sanitize all user inputs. Prevent prompt injection attacks. Rate limiting already implemented. | Input validation middleware | Low |
| H.6 | **Dependency scanning** — Automated vulnerability scanning for Python and Node.js dependencies. | Dependabot or similar | Low |
| H.7 | **Backup strategy** — Automated daily backup of SQLite DB and LanceDB to durable storage. | Backup script + cron | Low |

---

## Part 6: Phased Execution Plan

The workstreams above are independent, but there's a logical sequencing that maximizes value at each stage. Here's the recommended build order.

### Phase 4: Knowledge Depth + Consumer Wedge (Next 8–12 weeks)

**Goal:** Make the product genuinely useful for both audiences. Add case law (the missing foundation for attorneys), build the consumer assessment tool (the free acquisition wedge), and harden for production.

**Dependency graph:**

```
4A Infrastructure ──┐
                    ├── 4B Eyecite + CourtListener Client ──┐
                    │                                        ├── 4C Case Law Pipeline
                    │                                        └── 4D Citation Verification
                    │
                    ├── 4E Consumer Assessment Tools (independent)
                    ├── 4F SEO Content Pages (after 4E)
                    └── 4G Spanish Consumer UI (independent)
```

Critical path: 4A → 4B → 4C → 4D (~7–10 weeks). Consumer track (4E, 4F, 4G) runs in parallel with the case law chain. Every sub-phase has its own gate and test suite. Nothing ships without tests.

#### 4A — Infrastructure Foundation (1–2 weeks)

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4A.1 | **CI/CD pipeline** — GitHub Actions: run `uv run pytest` on every PR, deploy staging on merge to main, production with manual approval gate. | `.github/workflows/ci.yml` | CI runs 774 existing tests green on first PR |
| 4A.2 | **Error tracking** — Sentry integration for FastAPI backend and Next.js frontend. Alert on error rate spikes. | Sentry DSN configured, error captured in test | Sentry captures a test exception end-to-end |
| 4A.3 | **Privacy policy page** — CCPA/CPRA compliant. Documents: data collected (queries, feedback, IP), 90-day full retention then anonymization (per PO-8), user rights (know/delete/opt-out). | `/privacy` page (frontend) | Page renders, linked from footer, content covers required CCPA sections |
| 4A.4 | **Input sanitization** — Validate and sanitize all user inputs on API boundary. Prompt injection prevention (detect and reject adversarial prompts). | Input validation middleware in FastAPI | Unit tests: valid input passes, injection attempts blocked, oversized input rejected |

**[GATE 4A]** CI pipeline green on every PR. Sentry reporting errors. Privacy policy live. Input sanitization active.

---

#### 4B — Core Libraries: Eyecite + CourtListener Client (2–3 weeks)

These are the foundation libraries that the case law pipeline and citation verification both depend on.

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4B.1 | **Eyecite integration** — Python module wrapping the Eyecite library for citation extraction from legal text. Extract both case citations (e.g., "Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028") and statutory citations (e.g., "Gov. Code, § 12940, subd. (a)"). Normalize to standard format. | `src/employee_help/processing/citation_extractor.py` | Unit tests: extract case cites, statutory cites, mixed text, California-specific formats, edge cases (parentheticals, string cites, pin cites) |
| 4B.2 | **CourtListener API client** — Authenticated REST client for CourtListener v4 API. Endpoints: search opinions, fetch opinion text, fetch clusters, citation lookup. Pagination support (cursor-based). Rate limit handling (5,000 req/hr). Retry with backoff on transient errors. | `src/employee_help/scraper/extractors/courtlistener.py` | Unit tests (mocked HTTP via respx): search, fetch, pagination, rate limit 429 handling, retry on 500, auth header |
| 4B.3 | **Opinion loader** — Bulk download pipeline: paginate through CA Supreme Court + Courts of Appeal opinions via CourtListener API, run Eyecite on each opinion to extract cited statutes, filter to opinions citing employment statutes in our knowledge base (FEHA, Labor Code, UIC, B&P, CCP). Configurable court list and statute list for extensibility. | Opinion loader with configurable filters | Integration tests: filter pipeline correctly identifies employment opinions, rejects non-employment opinions, handles malformed opinion text |

**[GATE 4B]** Eyecite extracts citations from 20 sample opinions with >95% accuracy. CourtListener client can paginate through search results (verified against live API with 5 test queries). Opinion loader filters corpus to employment-relevant opinions.

---

#### 4C — Case Law Pipeline (2–3 weeks) — depends on 4B

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4C.1 | **Case law content category** — Add `CASE_LAW = "case_law"` to ContentCategory enum. Add to attorney mode retrieval categories. Exclude from consumer mode. | Updated `storage/models.py`, `retrieval/service.py` | Unit tests: attorney mode includes case_law, consumer mode excludes it |
| 4C.2 | **Case law chunking strategy** — New `case_law` chunking mode: extract opinion metadata (parties, court, date, case citation, docket number), split opinion into meaningful sections (background, analysis, holding), each chunk carries full case citation. Long opinions split at paragraph boundaries preserving citation context. | Enhanced `chunker.py` with `strategy: case_law` | Chunking tests: metadata extraction, long opinion splitting, citation on every chunk, short opinion stays single chunk |
| 4C.3 | **Citation linking table** — Run Eyecite over all ingested opinions. Build bidirectional links in SQLite: for each case, which statutes it cites; for each statute, which cases cite it. | New `citation_links` table in SQLite, CRUD methods in storage | Link table tests: citation counts match, bidirectional lookups work, deduplication, no orphaned links |
| 4C.4 | **Source config + pipeline integration** — Create `config/sources/courtlistener.yaml`. Integrate opinion loader into pipeline via new `_run_caselaw()` method. CLI command: `employee-help ingest-caselaw`. | Source config, pipeline method, CLI command | Pipeline test: end-to-end ingest of 10 test opinions, verify documents + chunks + links created |
| 4C.5 | **Embed and index case law** — Run embedding pipeline on case law chunks. Update LanceDB FTS index. Verify hybrid search returns case law for attorney queries. | Case law vectors in LanceDB | Retrieval tests: attorney query for "FEHA retaliation elements" returns case law; citation query for "Yanowitz" returns the case; consumer query returns zero case law |
| 4C.6 | **Full ingestion run** — Download and ingest CA state appellate employment opinions. Target: 2,000–5,000 opinions. | Populated case law knowledge base | Spot-check: 20 random opinions verified for correct citation, court, date, content quality |

**[GATE 4C]** 2,000+ employment opinions ingested and embedded. Attorney search returns case law alongside statutes. Consumer mode returns zero case law. Updated retrieval quality eval passes with `case_law` in expected categories.

---

#### 4D — Citation Verification (1–2 weeks) — depends on 4B, 4C

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4D.1 | **CourtListener case verification** — For every case citation in LLM output: query CourtListener API to verify case exists, check citation format matches, confirm California jurisdiction, validate year. Return verification result (verified/not_found/wrong_jurisdiction/date_mismatch). | `src/employee_help/generation/citation_verifier.py` | Unit tests (mocked API): valid CA case → verified, fake case → not_found, federal case → wrong_jurisdiction, wrong year → date_mismatch |
| 4D.2 | **Statute currency check** — For every statute citation: verify section exists and is active in PUBINFO (`active_flg = 'Y'`). Check if section was amended since last ingestion. | Statute verifier in `citation_verifier.py` | Unit tests: active section → verified, repealed → flagged, amended → warning with date |
| 4D.3 | **Confidence scoring** — Aggregate verification results into per-citation confidence: Verified (all checks pass), Unverified (case/statute not found in external source), Suspicious (wrong jurisdiction, date mismatch, repealed). | Confidence scoring logic | Scoring tests: all-pass → Verified, missing case → Unverified, repealed statute → Suspicious |
| 4D.4 | **Wire into answer generation** — Integrate citation verifier into AnswerService: after LLM generates response, extract citations via Eyecite, verify each, annotate response with confidence scores. Runs asynchronously to avoid blocking streaming. | Updated `generation/service.py` | E2E test: ask attorney question → response includes citations → each citation has confidence score |
| 4D.5 | **Confidence badges in UI** — Display verification status next to each citation: green checkmark (Verified), yellow question mark (Unverified), red warning (Suspicious). Tooltip shows verification details. | Frontend citation badge component | Frontend renders badges, tooltips display correct status text |
| 4D.6 | **Citation audit log** — Log every citation generated, verification status, verification source, and timestamp. CLI report: `employee-help citation-audit --since 2026-03-01`. | `citation_audit` table in SQLite, CLI command | Audit table populated after queries, CLI report shows correct counts |

**[GATE 4D]** Every citation in attorney mode output is mechanically verified. Run 25-question attorney eval: zero hallucinated citations, all citations carry confidence badges. Citation audit log captures all verification activity.

---

#### 4E — Consumer Assessment Tools (2–3 weeks) — parallel with 4B–4D

Independent of the case law chain. Can start as soon as 4A is complete.

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4E.1 | **Statute of limitations calculator** — Input: claim type + incident date. Output: all relevant deadlines (CRD 3yr, EEOC 300d, PAGA LWDA 1yr, govt tort 6mo, Labor Code varies by section). Urgency warnings for deadlines < 90 days. | Backend: `/api/deadlines` endpoint. Frontend: calculator component. | Unit tests: every claim type, boundary dates, expired deadlines, multiple overlapping deadlines. Edge cases: weekends, leap years. |
| 4E.2 | **Unpaid wages calculator** — Input: hours/week, hourly rate, breaks missed, weeks worked. Output: regular pay, daily overtime (>8hrs), weekly overtime (>40hrs), double time (>12hrs), meal break premiums (Lab. Code § 226.7), rest break premiums, waiting time penalties (Lab. Code § 203). | Backend: `/api/wages` endpoint. Frontend: calculator component. | Math unit tests: daily OT, weekly OT, double time, 7th-day premium, meal/rest premiums at regular rate, waiting time (30-day cap). Validate against known examples. |
| 4E.3 | **Agency routing guide** — Input: claim type(s). Output: which agency to file with (CRD vs. EEOC vs. DLSE vs. LWDA vs. court), step-by-step filing instructions, direct links to filing portals. Decision logic handles dual-filing scenarios (e.g., FEHA + Title VII → CRD cross-files with EEOC). | Backend: routing logic. Frontend: step-by-step guide component. | Routing logic tests: each claim type maps to correct agency, dual-filing detected, links validated |
| 4E.4 | **Guided intake questionnaire** — Multi-step conversational form. Steps: (1) What happened? (category selection), (2) When? (timeline), (3) Where? (employer info), (4) Protected characteristics? (if discrimination), (5) Reporting history (internal complaints, agency filings). Maps answers to claim categories. Prominent disclaimer at every step. | Backend: `/api/assess` endpoint. Frontend: `/assess` route with multi-step form. | Flow tests: complete path for each of 5 claim types (discrimination, wage theft, retaliation, wrongful termination, leave violation). Disclaimer present on every step. Incomplete submissions handled gracefully. |
| 4E.5 | **Rights summary generator** — After assessment, generate plain-language summary using RAG pipeline: "Based on what you've described, here are the California employment rights that may be relevant..." Includes statute citations, agency links, filing deadlines, and next steps. Strong disclaimer. | Backend: assessment → RAG query. Frontend: summary display with citations + disclaimer. | API tests: assessment data produces relevant summary with real citations. Disclaimer always present. Summary covers correct claim types for input. |

**[GATE 4E]** All calculators produce correct results for test vectors. Assessment flow completable for 5 claim types. Rights summary includes verified statute citations and disclaimer. All consumer tools render correctly on mobile (44px touch targets).

---

#### 4F — SEO Content Pages (1–2 weeks) — after 4E

Builds on 4E by linking to the interactive assessment tools and calculators from each content page.

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4F.1 | **8 claim-type landing pages** (SSG) — One per major claim type: wrongful termination, FEHA discrimination, FEHA harassment, wage theft, retaliation, PAGA, CFRA leave, misclassification. Each page includes: overview, elements of the claim, relevant statutes, filing deadlines, "Assess Your Situation" CTA linking to `/assess`, 5+ FAQs with schema.org FAQPage markup, internal links to related topics and calculators. | 8 new pages in `frontend/app/claims/[type]/page.tsx` | Build passes. Schema.org validates (Google Rich Results Test). Internal links resolve. CTA links to working assessment tool. |
| 4F.2 | **Calculator pages** — Standalone SEO-optimized pages wrapping the C.2 statute of limitations calculator and C.6 unpaid wages calculator. Each has its own URL, meta description, schema.org markup, and educational content above the calculator. | `/tools/overtime-calculator`, `/tools/deadline-calculator` pages | Pages render. Calculators functional. Schema.org markup present. |

**[GATE 4F]** 8 claim-type pages + 2 calculator pages live. All schema.org markup validates. Internal linking complete across topic pages, claim pages, and calculator pages.

---

#### 4G — Spanish Consumer UI (1–2 weeks) — parallel with 4B–4F

Independent track. Can start as soon as 4A is complete.

| # | Task | Deliverable | Tests |
|---|------|-------------|-------|
| 4G.1 | **API `language` parameter** — Add optional `language` field to AskRequest schema. When `language: "es"`, system prompt includes instruction: "Respond entirely in Spanish. Translate legal terms but include the English legal term in parentheses on first use." | Updated `schemas.py`, `prompts.py` | API test: Spanish query → Spanish response. English legal terms preserved in parentheses. Citations remain in English (statute numbers are language-neutral). |
| 4G.2 | **Spanish UI strings** — Extract all user-facing text (buttons, labels, headings, disclaimers, consent modal, error messages) into a locale system. Create Spanish translations. | `frontend/lib/i18n/` with `en.json` + `es.json` | String coverage test: every key in `en.json` has corresponding key in `es.json` |
| 4G.3 | **`/es` route prefix** — Next.js i18n routing: `/es` prefix loads Spanish locale, default (no prefix) is English. `hreflang` tags on all pages (`<link rel="alternate" hreflang="es">` and vice versa). Language toggle in header. | i18n config in `next.config.ts`, layout updates | Route test: `/es` loads Spanish UI. `/es/topics` loads Spanish topic page. `hreflang` tags present on every page. Language toggle switches between `/` and `/es`. |
| 4G.4 | **Spanish assessment flow** — Ensure guided intake questionnaire (4E.4), rights summary (4E.5), and calculators (4E.1, 4E.2) all work in Spanish using the locale strings and Spanish LLM responses. | Assessment flow functional in Spanish | E2E test: Spanish user completes assessment → receives Spanish rights summary with English citations |
| 4G.5 | **Spanish topic pages** — Translate top 5 existing topic pages to Spanish (SSG). | `/es/topics/[slug]` pages | Pages render. `hreflang` tags cross-link English ↔ Spanish versions. |

**[GATE 4G]** Spanish user can: visit `/es` → browse topics in Spanish → ask question in Spanish → receive Spanish response → complete assessment in Spanish → view deadline calculator in Spanish. All disclaimers rendered in Spanish.

---

#### Phase 4 Summary

| Sub-phase | Duration | Depends On | Parallel With | Key Deliverable |
|-----------|----------|-----------|---------------|----------------|
| **4A** Infrastructure | 1–2 wks | — | — | CI/CD, Sentry, privacy policy, input sanitization |
| **4B** Core Libraries | 2–3 wks | 4A | 4E, 4G | Eyecite + CourtListener client + opinion loader |
| **4C** Case Law Pipeline | 2–3 wks | 4B | 4E, 4F, 4G | 2,000+ opinions ingested, case law in attorney search |
| **4D** Citation Verification | 1–2 wks | 4B, 4C | 4F, 4G | Every citation mechanically verified, confidence badges |
| **4E** Consumer Assessment | 2–3 wks | 4A | 4B, 4C, 4D | Calculators, assessment flow, rights summary |
| **4F** SEO Pages | 1–2 wks | 4E | 4D, 4G | 8 claim pages + 2 calculator pages |
| **4G** Spanish UI | 1–2 wks | 4A | 4B–4F | Full Spanish consumer experience |

**Critical path:** 4A → 4B → 4C → 4D = ~7–10 weeks
**Total with parallelism:** ~8–12 weeks
**Tests added (estimated):** ~150–200 new tests across all sub-phases

**Phase 4 Exit Criteria:**
- [ ] Case law in knowledge base: 2,000+ CA state appellate employment opinions
- [ ] Citation verification pipeline operational: zero hallucinated citations in 25-question eval
- [ ] Consumer assessment flow live for 5 claim types
- [ ] Statute of limitations calculator and unpaid wages calculator functional
- [ ] 8 claim-type landing pages + 2 calculator pages live with schema.org markup
- [ ] Spanish consumer experience functional (`/es` route, Spanish LLM responses)
- [ ] CI/CD pipeline operational: tests run on every PR, staging auto-deploy
- [ ] Privacy policy live, Sentry tracking errors, input sanitization active
- [ ] Total test count: 900+ (current 774 + ~150–200 new)

### Phase 5: Attorney Workflow + Knowledge Expansion (Following 8–12 weeks)

**Goal:** Build the features attorneys will pay for. Ship tools that save measurable time. Expand the knowledge base with interpretive authorities.

| Track | Workstream Items | Why Now |
|-------|-----------------|---------|
| **Attorney Tools** | D.1, D.4, D.5, D.6 | Demand letter generator, deadline tracker, intake screener, and export tools. These are the revenue features — what attorneys pay $99–149/month for. |
| **Knowledge Expansion** | E.1, E.2, E.3, E.6 | DLSE opinion letters, enforcement manual, wage orders, Legal Aid fact sheets. Fill the gaps that make the research tool authoritative. |
| **Legislative Tracking** | B.1, B.2, B.3 | Automated refresh, "What's New" digest, currency indicators. This is the "annual update problem" solved — worth a subscription on its own. |
| **Consumer Enhancements** | C.4, C.6 | Incident documentation helper, unpaid wages calculator. Deepen the consumer experience. |

**Exit criteria:**
- Demand letter generator functional for 3+ claim types
- Intake screening tool functional
- DLSE opinion letters and enforcement manual ingested
- Automated weekly knowledge base refresh operational
- "What's New" digest publishable

### Phase 6: Marketplace Foundation + Scale (Following 8–12 weeks)

**Goal:** If consumer traffic and attorney adoption metrics justify it, build the two-sided marketplace. This is the network-effects play.

| Track | Workstream Items | Why Now |
|-------|-----------------|---------|
| **Attorney Portal** | Account creation, subscription management (Stripe), usage dashboard, saved research | Revenue infrastructure |
| **Discovery Templates** | D.2, D.3 | CRD complaint assistant, discovery request templates. Deeper litigation workflow. |
| **Advanced KB** | A.4, E.4, E.5, E.7 | Harvard CAP historical backfill, CCR regulations, EEOC guidance. Full knowledge coverage. |
| **Multilingual** | G.4 | Spanish language pages. Unlock the 7M+ limited-English-proficiency California workers. |
| **Marketplace Prep** | Attorney profiles, lead routing logic, flat-fee billing | Only if consumer traffic justifies it |

> **Note:** Phase 6 timing and scope should be re-evaluated based on Phase 4–5 metrics. Per PO-1, the marketplace uses a flat-fee advertising model (Option A) when consumer traffic justifies it. Do not build prematurely.

---

## Part 7: Revenue Model

### Near-Term (Phase 4–5): SaaS + Freemium

| Tier | Price | What's Included | Target |
|------|-------|----------------|--------|
| **Consumer Free** | $0 | Rights chatbot (5 queries/day), assessment tool, calculators, filing guides | Workers with employment issues |
| **Consumer Premium** | $19–29/month | Unlimited queries, incident documentation, detailed analysis, email alerts | Workers with active cases |
| **Attorney Professional** | $99–149/month | Unlimited research, demand letter generator, intake screening, deadline tracker, export tools, case law search | Solo practitioners, small firms |
| **Attorney Firm** | $149–249/month (2–5 seats) | Team features, shared research, firm-wide templates | Small employment firms |

**Unit economics at $99/month attorney subscription:**
- LLM cost per attorney (est. 20 queries/day): ~$0.64/day = ~$19.20/month
- Infrastructure cost per user: ~$2–5/month
- Gross margin: ~75–80%
- Break-even: ~15 paying attorneys covers $1,500/month infrastructure

**Pricing positioning:** Below CoCounsel ($225–500/user/month) and Harvey (enterprise pricing). Above generic AI tools ($20/month ChatGPT). Within the solo practitioner budget ($250/month total tech spend per ABA data). A tool that saves 5 hours/month generates $2,100 in value at $420/hour — $99/month is a 21x ROI.

### Medium-Term (Phase 6+): Lead Generation

| Revenue Stream | Model | Estimated Revenue |
|----------------|-------|-------------------|
| **Qualified leads** | Flat fee per lead ($200–500) | Depends on traffic volume |
| **Attorney directory** | Monthly listing fee ($50–100) | Recurring |
| **Featured placement** | Premium positioning ($200–500/month) | Recurring |

> **PO-1 resolved:** Tools only for now. Flat-fee advertising model (Option A) is the intended future direction once consumer traffic justifies it.

### Long-Term Vision: Settlement Data Moat

Every case flowing through the platform (with consent) builds a proprietary settlement database: outcomes by claim type, employer size, jurisdiction, damages. This is what made EvenUp worth $2B. No one has this dataset for California employment law. It becomes exponentially more valuable over time.

---

## Part 8: Key Metrics

### Product Metrics

| Metric | Current | Phase 4 Target | Phase 5 Target |
|--------|---------|---------------|---------------|
| Knowledge base chunks | 24,106 | 35,000+ (with case law) | 50,000+ (with CCR, DLSE) |
| Citation accuracy (verified) | 73% completeness | 95%+ with external verification | 98%+ |
| Consumer assessments/month | 0 | 500+ | 2,000+ |
| Attorney research queries/month | 0 | 200+ | 1,000+ |
| 7-day return rate (consumer) | N/A | >20% | >30% |
| 7-day return rate (attorney) | N/A | >40% | >60% |
| Feedback score (thumbs up %) | N/A | >70% | >80% |

### Business Metrics

| Metric | Phase 4 Target | Phase 5 Target | Phase 6 Target |
|--------|---------------|---------------|---------------|
| Monthly active users | 100+ | 500+ | 2,000+ |
| Paying attorney subscribers | 0 (free beta) | 20+ | 75–100 |
| MRR | $0 | $2,000+ | $10,000+ |
| Per-query cost (blended) | $0.015 | $0.012 (optimize) | $0.010 |
| SEO organic traffic/month | <100 | 1,000+ | 5,000+ |

---

## Part 9: PO Decisions (All Resolved 2026-02-28)

| # | Decision | Resolution |
|---|----------|-----------|
| PO-1 | **Attorney marketplace legal structure** | **Option C: Tools only, no marketplace.** Flat-fee advertising (Option A) is the intended future direction once consumer traffic justifies it. Architect consumer assessment to capture structured data that could fuel lead routing later, without building routing now. |
| PO-2 | **Disclaimer language review** | **Flagged for dedicated review pass.** PO (licensed attorney) will review all disclaimer text (consent modal, inline disclaimer, terms page) as a separate task. Not a build blocker. |
| PO-3 | **Case law ingestion scope** | **CA state appellate only.** California Supreme Court + Courts of Appeal opinions citing statutes already in our knowledge base. Federal (Ninth Circuit, CA district courts) revisited based on attorney feedback. Pipeline built to be extensible — adding federal is a config change, not a code change. |
| PO-4 | **Attorney tool prioritization** | **D.5 (intake screening) + D.1 (demand letters) first.** These solve the #1 and #2 attorney pain points. D.6 (export/copy) and D.4 (deadline tracker) ship alongside as quick wins. |
| PO-5 | **LDA registration** | **Deferred.** All document generation features (demand letters, complaints, discovery) are attorney-mode only. This avoids LDA registration requirements. Revisit if consumer-facing document generation is added. |
| PO-6 | **Pricing validation approach** | **Free for now, add payments later.** Launch all features free to accumulate users and usage data. Add Stripe payments once we have 20+ active attorneys and can validate willingness to pay with real data. No payment infrastructure needed in Phase 4–5. |
| PO-7 | **Spanish language priority** | **Phase 4 — consumer UI and LLM responses only.** Spanish UI strings, `/es` route prefix, `language` parameter so Claude responds in Spanish. No knowledge base translation needed — the legal authority is the same. The LLM already speaks Spanish; we just need the UI and routing layer. |
| PO-8 | **Data retention policy** | **90-day full retention, then anonymize.** Keep full query logs (including IP) for 90 days for quality improvement and debugging. After 90 days, strip IP addresses and PII, keep anonymized query + response for aggregate analytics indefinitely. |

---

## Part 10: What Success Looks Like

### 6-Month Horizon (End of Phase 5)
- **Knowledge base**: 50,000+ chunks across statutes, case law, regulations, agency guidance, jury instructions, opinion letters
- **Consumer**: 2,000+ assessments/month driven by organic SEO. Workers using the tool to understand their rights and take action.
- **Attorney**: 20+ paying subscribers at $99–149/month. Demand letter generator and intake screening saving measurable hours per week.
- **Citation accuracy**: 98%+ verified citations. Zero hallucinated cases in production. Demonstrably better than Westlaw AI (33% hallucination) and Lexis+ AI (17%).
- **Revenue**: $2,000+ MRR from attorney subscriptions.

### 12-Month Horizon (End of Phase 6)
- **The two-sided marketplace**: Consumer assessment → attorney matching → case progression. Network effects beginning.
- **Attorney**: 75–100 paying subscribers. $10,000+ MRR.
- **SEO**: 5,000+ organic visitors/month. Top 10 rankings for core California employment law queries.
- **Data moat**: Case flow data accumulating. Settlement database embryonic but growing.
- **Positioning**: "The only legal AI that actually knows California employment law." Verified citations. Annual update coverage. Practice-area depth that generic tools can't match.

### The Contrarian Bet (Zero to One)

> "What important truth do very few people agree with you on?"

Most people believe legal AI tools are either (a) too unreliable for serious use, or (b) must be expensive enterprise products. Our bet: **a niche-specific AI platform built on free public-domain data, with verified citations and practice-area depth, can be both trustworthy enough for attorneys to cite and affordable enough for solo practitioners to use daily.** If true, the 87% of law firms that are priced out of Harvey and CoCounsel become our market. California employment law — with 10,000+ annual PAGA filings, 30,000+ CRD intakes, and 1,400+ organized plaintiff attorneys — is the ideal beachhead.

The window is open but closing. Clio's vLex acquisition ($1B), Harvey's growth ($195M ARR), and Thomson Reuters' CoCounsel expansion are all moving toward this space from the enterprise end. The advantage goes to whoever builds the curated knowledge base, the citation verification pipeline, and the practice-area-specific workflows — and gets them into the hands of CELA's 1,400 members before anyone else does.

Build it. Ship it. The lawyers will come.
