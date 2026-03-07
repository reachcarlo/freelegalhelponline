# Gap Analysis & Implementation Roadmap

> **Date**: 2026-03-06 (corrected)
> **Purpose**: Identify all planned-but-unimplemented features across documentation, prioritized for pre-litigation and litigation attorneys
> **Method**: Systematic audit of EXPANDED_REQUIREMENTS.md, PRODUCT_REQUIREMENTS_2.md, OBJECTIONS.md, DISCOVERY_TOOLS.md cross-referenced against actual backend/frontend codebase and live database state

---

## Current State Summary

### What's Built and Working

| Area | Status |
|------|--------|
| **Knowledge Base** | 54,605 active chunks from 20 sources (9 statutory, 3 agency, 4 regulatory/guidance, 1 CACI, 1 case law, 2 additional statutory) |
| **RAG Pipeline** | Hybrid search (vector + BM25 + RRF), dual-mode (consumer/attorney), Claude Citations API |
| **Web MVP** | FastAPI backend + Next.js frontend, SSE streaming, multi-turn conversation |
| **Discovery Request Generation** | FROGs (general + employment), SROGs, RFPDs, RFAs — complete wizard flows with DOCX/PDF export |
| **Objection Drafter (O.1-O.2B)** | Paste + file upload input, parser, LLM analysis, citation validation, 4-step wizard, verbosity control, litigation posture, Word export, shell insertion |
| **Consumer Assessment** | Guided intake, statute of limitations calculator, unpaid wages calculator, agency routing, rights summary |
| **Case Law** | 14,552 chunks from CA appellate opinions (CourtListener), attorney-mode retrieval |
| **Regulatory Sources** | CCR Title 2 FEHA (110 chunks), CCR Title 8 (8,803 chunks), DLSE Manual (146 chunks), EEOC guidance (2,073 chunks) |
| **Additional Statutory** | Civil Code (2,647), Education Code (2,199), Health & Safety Code (432) |
| **Citation Verification** | Eyecite extraction, CourtListener case verification, statute currency, confidence scoring + badges |
| **Claim Pages** | 8 claim-type landing pages (SSG) at `/claims/[type]` |
| **SEO Topic Pages** | 11 topic pages with FAQPage schema.org |
| **Infrastructure** | Railway (backend) + Vercel (frontend), rate limiting, CORS, Sentry, input sanitization, privacy page |
| **Tests** | 1,553 passing |

---

## Identified Gaps (Planned but Not Implemented)

### A. Objection Drafter Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| A.1 | **O.3 — Template Editor**: Pill-based tag insertion UI, 3 built-in presets, separator dropdown, localStorage persistence, live preview | OBJECTIONS.md §O.3 | Medium — gated on user feedback |
| A.2 | **O.4 — Per-request controls**: Single-request regenerate, inline text editing, desktop two-column synchronized scroll layout, optional case context field, smart strength defaults | OBJECTIONS.md §O.4 | High — directly improves attorney UX |
| A.3 | **O.5 — Firm language overrides**: Per-ground custom language, server-side persistence (requires auth), learning from attorney choices | OBJECTIONS.md §O.5 | Low — requires auth system |
| A.4 | **Live LLM acceptance testing**: Posture differentiation (aggressive > balanced > selective objection count), partial failure handling, batch cost/perf validation | OBJECTIONS.md §O.2A acceptance criteria | Medium |
| A.5 | **Analytics logging**: Posture value, verbosity, discovery type logged for conversion tracking | OBJECTIONS.md §O.2A | Low |

### B. Discovery Response Workflow Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| B.1 | **Client Input Bridge**: Translate requests to plain English for client, receive structured answers for substantive responses | OBJECTIONS.md §7.1 | Medium — future phase |
| B.2 | **Substantive Response Drafting**: RAG-powered discovery responses using case facts + KB | OBJECTIONS.md §7.1 | High — major attorney workflow value |
| B.3 | **Meet-and-Confer Preparation**: Detailed rationale generation for each objection, CCP §2016.040 compliance | OBJECTIONS.md §7.1 | Medium |
| B.4 | **Privilege Log Generation**: Auto-generated log for privilege/work product objections, CCP §2031.240(c)(1) | OBJECTIONS.md §7.1 | Medium |
| B.5 | **Response Document Assembly**: Combine objections + responses + verification into complete response document | OBJECTIONS.md §7.1 | High — full workflow completion |

### C. Attorney Workflow Tool Gaps (Workstream D)

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| C.1 | **D.1 — Demand letter generator**: Template-based drafting with real citations, 6+ claim types, structured intake, DOCX/PDF output marked "DRAFT" | PRD2 Workstream D | High — #1 attorney pain point per PO-4 |
| C.2 | **D.2 — CRD complaint draft assistant**: Guided walkthrough, pre-populate from intake, narrative statement generation | PRD2 Workstream D | Medium |
| C.3 | **D.4 — Employment law deadline tracker**: Dashboard of all case-relevant deadlines, auto-calculated from case start date | PRD2 Workstream D | Medium — quick win |
| C.4 | **D.5 — Case intake screening tool**: AI-powered pre-screening with viability assessment, claim types, SOL status, potential damages | PRD2 Workstream D | High — #2 attorney pain point per PO-4 |
| C.5 | **D.6 — Export and copy tools**: Copy citation, copy analysis section, export full answer to Word/PDF formatted for briefs | PRD2 Workstream D, EXPANDED_REQS §5A.5 | High — reduces workflow friction |
| C.6 | **D.7 — Research session memory**: Save/resume research sessions, tag by case, search across saved research | PRD2 Workstream D | Medium — requires auth |
| C.7 | **Attorney onboarding & discoverability**: Tool landing page, feature tour, getting-started guide — attorneys must discover existing tools to use them | PM analysis | High — adoption blocker |

### D. Knowledge Base Expansion Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| D.1 | **DLSE Opinion Letters**: Config exists (`dlse_opinions.yaml`) but no extractor implemented, not in DB. PDF scraping from dir.ca.gov, `opinion_letter` content category | PRD2 Workstream E | High — courts give "great weight" |
| D.2 | **IWC Wage Orders**: 17 industry-specific wage orders, cross-reference to statutes. No config exists. | PRD2 Workstream E | Medium — critical for wage-and-hour |
| D.3 | **Legal Aid at Work fact sheets**: Config exists, source registered, but 0 documents/0 chunks ingested. Scraper needs debugging. | PRD2 Workstream E | Low — consumer content |
| D.4 | **Harvard CAP historical backfill**: Pre-2018 case law from HuggingFace (CC0) | PRD2 Workstream A.4 | Low |
| D.5 | **CalHR oversized chunk**: 1 chunk at 37,820 tokens; heading-based chunker needs max-size enforcement | MEMORY.md, cross-validation | Low — single known issue |

> **Note**: The following were listed as gaps in the initial audit but are confirmed **already implemented** with active data:
> CCR Title 2 FEHA (110 chunks), CCR Title 8 (8,803 chunks), DLSE Enforcement Manual (146 chunks),
> EEOC guidance (2,073 chunks), Civil Code (2,647 chunks), Education Code (2,199 chunks),
> Health & Safety Code (432 chunks). These were ingested as of 2026-03-05.

### E. Legislative Tracking & Currency Gaps (Workstream B)

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| E.1 | **B.1 — Automated weekly refresh**: Scheduled PUBINFO re-download, diff, re-embed changed chunks | PRD2 Workstream B | High — without this, KB decays |
| E.2 | **B.2 — "What's New" digest**: Auto-generated statutory change summary, publishable as newsletter | PRD2 Workstream B | Medium — retention/marketing |
| E.3 | **B.3 — Statute currency indicator**: Warning badge when cited statute was amended since ingestion | PRD2 Workstream B | High — attorney trust |
| E.4 | **B.4 — LegiScan integration**: Pending bill alerts for cited statutes | PRD2 Workstream B | Low |

### F. Infrastructure & Quality Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| F.1 | **4A.1 — CI/CD pipeline**: GitHub Actions, tests on PR, staging on merge, production with approval gate | PRD2 §4A, EXPANDED_REQS §4A | High — operational necessity |
| F.2 | **4A.3 — Privacy policy content review**: Page exists but needs attorney review of content | PRD2 §4A | Medium |
| F.3 | **Dependency vulnerability scanning**: Dependabot or similar | PRD2 Workstream H | Low |
| F.4 | **Backup strategy**: Automated daily backup of SQLite + LanceDB | PRD2 Workstream H | Medium |
| F.5 | **Operational runbooks**: Content refresh, incident response, backup/recovery | EXPANDED_REQS §4A.5 | Medium |
| F.6 | **Legal disclaimer attorney review**: PO (licensed attorney) to review all disclaimer text | PRD2 §4.2 | High — legal compliance |
| F.7 | **No PII collection verification**: Verify queries with sensitive info are not logged in production | EXPANDED_REQS §4A.4 | Medium |

### G. SEO & Content Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| G.1 | **4F.2 — Calculator SEO pages**: Standalone pages wrapping SOL and wages calculators with educational content | PRD2 §4F | Low |
| G.2 | **G.2 — "What's New" blog**: Monthly automated employment law changes digest as SSG pages | PRD2 Workstream G | Low — depends on E.1 |
| G.3 | **Content marketing pillar articles**: 10 articles on high-volume topics | EXPANDED_REQS §4B.2 | Low |

### H. Spanish Language Gaps (4G)

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| H.1 | **API `language` parameter**: `language: "es"` on AskRequest, Spanish system prompt instruction | PRD2 §4G | Low for attorney focus |
| H.2 | **Spanish UI strings**: i18n locale system, `en.json` + `es.json` | PRD2 §4G | Low for attorney focus |
| H.3 | **`/es` route prefix**: Next.js i18n routing, hreflang tags, language toggle | PRD2 §4G | Low for attorney focus |

### I. Retention & Engagement Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| I.1 | **5A.2 — Feedback-driven quality loop**: Aggregate thumbs-down by topic, identify pain topics, weekly review cadence | EXPANDED_REQS §5A.2 | High — product quality |
| I.2 | **5A.3 — Suggested follow-up questions**: Context-generated clickable follow-ups after each answer | EXPANDED_REQS §5A.3 | Medium |
| I.3 | **5A.4 — Guided complaint filing workflow**: Step-by-step wizard (issue → agency → documents → file) | EXPANDED_REQS §5A.4 | Medium — consumer feature |
| I.4 | **Persistent conversation history**: Requires user accounts, server-side storage | EXPANDED_REQS §5A.1 | Low — requires auth |

### J. Platform & Revenue Gaps

| ID | Gap | Source Doc | Severity |
|----|-----|-----------|----------|
| J.1 | **Attorney portal**: Account creation, authentication, usage dashboard, billing | PRD2 §4C.3, EXPANDED_REQS §4C | Medium — pre-revenue |
| J.2 | **Payment infrastructure (Stripe)**: Subscription management, free tier enforcement | PRD2 §4C.2, EXPANDED_REQS §4C | Medium — pre-revenue |
| J.3 | **5C.1 — Cross-reference sidebar**: Related statutes inline display for attorney mode | EXPANDED_REQS §5C.1 | Medium |
| J.4 | **5C.3 — API access**: RESTful API with auth, rate limiting, usage billing for legal tech integrations | EXPANDED_REQS §5C.3 | Low — enterprise |
| J.5 | **5C.4 — Statutory change alerts**: Email notification to subscribed attorneys on statute amendments | EXPANDED_REQS §5C.4 | Low — requires auth |
| J.6 | **Referral / share mechanism**: "Share this answer" with pre-loaded question URL | EXPANDED_REQS §4B.3 | Low |

---

## Prioritized Implementation Roadmap

Given the stated focus on **pre-litigation and litigation attorneys**, gaps are prioritized by:
1. **Direct workflow impact**: Does this save attorney time on tasks they do daily?
2. **Trust & accuracy**: Does this make the tool more trustworthy for professional use?
3. **Revenue enablement**: Does this justify a $99-149/month subscription?

### Phase R0: Quick Wins & Operational Foundation (1-2 weeks)

**Why first**: These are high-impact items that can ship immediately with minimal effort. Copy/export removes the most common friction point. CI/CD is required to ship everything else confidently. Currency badges are a trust signal attorneys notice on first use.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P0 | **Copy/export tools** — Copy citation, copy analysis, export to Word/PDF for briefs | C.5 | 3-5 days | Highest — removes friction in every session |
| P0 | **CI/CD pipeline** — Tests on PR, staging, production gate | F.1 | 2-3 days | High — operational necessity for shipping confidently |
| P0 | **Statute currency indicator** — Badge when statute amended since ingestion | E.3 | 3-4 days | High — attorney trust signal |
| P1 | **PII audit** — Verify no raw queries logged in production | F.7 | 1-2 days | Medium — compliance |

**Exit criteria**: Attorneys can copy/export answers into briefs. PRs run tests automatically. Amended statutes show visual warning.

---

### Phase R1: Attorney Workflow Essentials (3-5 weeks)

**Why second**: These are the features that turn Employee Help from a research tool into a workflow tool. An attorney who can draft a demand letter, screen an intake, and navigate the tool effectively will pay for the product.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P0 | **Demand letter generator** — Template-based with real citations, 6 claim types, DOCX output | C.1 | 2-3 weeks | Highest — solves #1 pain point |
| P0 | **Attorney onboarding & discoverability** — Tools landing page, feature tour, getting-started guide | C.7 | 3-4 days | High — adoption blocker (no value if tools aren't found) |
| P1 | **Case intake screening** — AI-powered pre-screening with viability assessment | C.4 | 1.5-2 weeks | High — #2 attorney pain point |

**Exit criteria**: Attorney can draft a demand letter with verified citations, screen case intakes, and easily discover all available tools.

---

### Phase R2: Objection Polish + Discovery Responses (4-5 weeks, interleaved)

**Why interleaved**: Objection O.4 and discovery responses are the same workflow domain. Building them together avoids context-switching. The objection improvements are quick, high-value UX wins; discovery responses complete the full discovery lifecycle.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P0 | **Objection drafter O.4** — Per-request regenerate, inline editing, two-column desktop layout | A.2 | 1-1.5 weeks | High — direct UX improvement for current tool |
| P0 | **Substantive response drafting** — RAG-powered responses to discovery requests | B.2 | 2-2.5 weeks | High — completes the discovery workflow |
| P1 | **Privilege log generation** — Auto-generated from privilege objections | B.4 | 3-4 days | Medium — saves tedious work |
| P1 | **Response document assembly** — Combine objections + responses into complete document | B.5 | 4-5 days | High — end-to-end output |

**Exit criteria**: Attorney uploads a discovery shell → gets complete response document with objections, substantive responses, and privilege log — ready for review and filing. Objection drafter supports inline editing and two-column review.

---

### Phase R3: Citation Trust & Quality (2-3 weeks)

**Why here**: Attorney trust is existential. The automated refresh prevents knowledge decay, and the feedback loop drives systematic quality improvement. These make the platform trustworthy for professional reliance.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P0 | **Automated weekly refresh** — Scheduled PUBINFO re-download, diff, re-embed | E.1 | 1-1.5 weeks | Highest — prevents trust erosion |
| P1 | **Feedback-driven quality loop** — Thumbs-down aggregation, pain topic identification | I.1 | 3-4 days | High — systematic quality improvement |
| P1 | **"What's New" digest** — CLI command generating statutory changes summary | E.2 | 2-3 days | Medium — retention + marketing |
| P1 | **Legal disclaimer attorney review** | F.6 | 1 day (PO task) | High — legal compliance |

**Exit criteria**: Knowledge base refreshes weekly without manual intervention. Product team has a weekly quality review cadence driven by feedback data.

---

### Phase R4: Knowledge Depth & Attorney Experience (2-3 weeks)

**Why here**: With the core workflow tools built and the refresh pipeline running, fill the remaining KB gaps and add experience polish features.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P0 | **DLSE Opinion Letters** — PDF ingestion from dir.ca.gov, new extractor | D.1 | 1 week | High — courts give "great weight" |
| P1 | **IWC Wage Orders** — 17 industry-specific orders, config + extractor | D.2 | 3-4 days | Medium — critical for wage-and-hour |
| P1 | **Employment law deadline tracker** — Dashboard with auto-calculated deadlines | C.3 | 3-5 days | Medium — quick win |
| P2 | **Cross-reference sidebar** — Related statutes shown inline in attorney answers | J.3 | 4-5 days | Medium — differentiator |

**Exit criteria**: Attorney wage-and-hour queries retrieve DLSE opinion letters and IWC wage orders alongside statutes. Deadline tracker shows all case-relevant deadlines.

---

### Phase R5: Remaining Polish (2-3 weeks)

**Why here**: With core tools, discovery workflow, and KB depth complete, these features improve daily usability and stickiness.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P1 | **Objection template editor (O.3)** — Pill-based, 3 presets, localStorage | A.1 | 1-1.5 weeks | Medium — gated on user feedback |
| P1 | **Meet-and-confer preparation** — Detailed rationale for each objection | B.3 | 2-3 days | Medium — CCP §2016.040 compliance |
| P1 | **Suggested follow-up questions** — Context-generated clickable follow-ups | I.2 | 2-3 days | Medium |
| P2 | **Backup strategy** — Automated daily backup of SQLite + LanceDB | F.4 | 2-3 days | Medium — operational safety |
| P2 | **Operational runbooks** — Refresh, incident response, recovery | F.5 | 2-3 days | Medium |
| P2 | **Dependency scanning** — Dependabot for Python + Node.js | F.3 | 1 day | Low |

**Exit criteria**: Attorneys have a customizable template system for objections, meet-and-confer rationales, and follow-up suggestions.

---

### Phase R6: Revenue Infrastructure (3-4 weeks)

**Why last in this plan**: Per PO-6, payments are deferred until 20+ active attorneys. But the architecture should be planned.

| Priority | Item | Gap ID | Effort | Impact |
|----------|------|--------|--------|--------|
| P2 | **Attorney portal** — Account creation, OAuth, usage dashboard | J.1 | 2-3 weeks | Medium — pre-revenue |
| P2 | **Payment infrastructure** — Stripe subscriptions, free tier enforcement | J.2 | 1-2 weeks | Medium — revenue enablement |
| P2 | **Research session memory** — Save/resume, tag by case | C.6 | 1-1.5 weeks | Medium — requires auth |

---

### Deferred (Not Prioritized for Attorney Focus)

These items are in the documentation but intentionally deprioritized given the attorney focus:

| Item | Gap ID | Reason to Defer |
|------|--------|----------------|
| Spanish language (4G) | H.1-H.3 | Consumer-focused; attorney workflow is English |
| Guided complaint filing wizard | I.3 | Consumer-focused |
| Content marketing articles | G.3 | Marketing, not product |
| Calculator SEO pages | G.1 | Consumer SEO, low attorney impact |
| Harvard CAP backfill | D.4 | Pre-2018 cases; current coverage sufficient |
| Legal Aid fact sheets | D.3 | Consumer content; needs scraper debug (0 chunks despite config) |
| CRD complaint draft assistant | C.2 | Medium priority; CRD process changing |
| Multi-state expansion | EXPANDED_REQS §5C.5 | Only after CA PMF proven |
| API access for legal tech | J.4 | Enterprise play, later |
| Attorney marketplace | PRD2 Phase 6 | Per PO-1, tools only for now |
| O.5 — Firm language overrides | A.3 | Requires auth, low demand signal |
| Client input bridge | B.1 | Future workflow enhancement |
| Persistent conversation history | I.4 | Requires auth infrastructure |
| Share/referral mechanism | J.6 | Growth feature, not workflow |
| LegiScan integration | E.4 | Low priority, after refresh is working |
| CalHR oversized chunk fix | D.5 | Single known issue, low impact |
| Analytics logging (posture/verbosity) | A.5 | Low, do with auth/portal |
| LLM acceptance testing | A.4 | Medium, do when adding CI test suite |

---

## Summary: Total Effort Estimate

| Phase | Focus | Duration | Key Deliverables |
|-------|-------|----------|------------------|
| **R0** | Quick Wins & Ops Foundation | 1-2 weeks | Copy/export, CI/CD, currency badges, PII audit |
| **R1** | Attorney Workflow Essentials | 3-5 weeks | Demand letters, onboarding, intake screening |
| **R2** | Objection Polish + Discovery Responses | 4-5 weeks | O.4, substantive responses, privilege log, document assembly |
| **R3** | Citation Trust & Quality | 2-3 weeks | Automated refresh, quality loop, "What's New" digest |
| **R4** | Knowledge Depth & Experience | 2-3 weeks | DLSE opinions, IWC wage orders, deadline tracker, cross-refs |
| **R5** | Remaining Polish | 2-3 weeks | Template editor, meet-and-confer, follow-ups, ops hardening |
| **R6** | Revenue Infrastructure | 3-4 weeks | Attorney portal, Stripe, session memory |

**Total**: ~17-25 weeks for all phases. Phases R0-R1 (~4-7 weeks) ship the fastest, highest-impact value. Phases R2-R3 (~6-8 weeks) complete the discovery workflow and trust infrastructure. Phases R4-R5 (~4-6 weeks) fill KB depth and polish. Phase R6 (~3-4 weeks) prepares for monetization.

---

## Architectural Notes

1. **Copy/export tools (C.5)** should be a thin layer over the existing `generation/models.py` Answer dataclass — format the answer text + citations into DOCX using the existing `discovery/generator/docx_builder.py`.

2. **Demand letter generator (C.1)** can reuse the existing DOCX builder and the existing intake questionnaire data model from `tools/intake.py`. The claim-type templates are new but follow the same `str.format_map()` pattern as objection templates.

3. **Knowledge base expansion (D.1-D.2)** follows established patterns: source YAML config → extractor → chunker → storage → embed. The source registry architecture means each is a config + extractor addition, no pipeline changes.

4. **Automated refresh (E.1)** builds on the existing `refresh` CLI command and `RefreshConfig` per-source YAML. The GitHub Actions workflow at `.github/workflows/refresh.yml` already exists as a skeleton — needs the diff/re-embed logic.

5. **Substantive response drafting (B.2)** reuses the existing objection parser for request extraction and the RAG pipeline for generating responses. The key new component is a prompt template that generates substantive responses rather than objections.

6. **Attorney onboarding (C.7)** is a frontend-only task: a `/tools` landing page showing all available tools organized by workflow stage (intake → research → discovery → drafting), with brief descriptions and direct links.
