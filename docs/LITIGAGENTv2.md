# LITIGAGENTv2 — The Junior Associate

> **Status**: IN PROGRESS — V2.3b COMPLETE
> **Predecessor**: [LITIGAGENT.md](./LITIGAGENT.md) (Phases L1–L3, the foundation)
> **Date**: 2026-03-23

---

## 1. The Insight

Everything starts with files.

An attorney doesn't open a tool and then go find their case. They're already working a case — they have a stack of documents, and they need someone to *do something* with them. The current product has powerful tools (discovery generation, objection drafting, case file chat) that each live in isolation. An attorney who wants to chat about a complaint, then draft discovery based on it, then prepare objections to the other side's requests, must navigate to three separate tools, re-enter case information three times, and maintain context in their head.

**LITIGAGENTv2 eliminates that friction.** The case workspace becomes the single environment for all attorney work. Upload files once. Extract metadata once. Every tool inherits the context. Toggle between tasks the way you'd hand assignments to a junior associate sitting across from you — "read this complaint," "draft interrogatories," "respond to these RFAs," "write me a demand letter" — and they just do it, because they already know the case.

### The Junior Associate Metaphor

Imagine walking into a junior associate's office. Their desk has every case document organized and tabbed. They've read everything. They know the parties, the claims, the timeline, the key facts. You don't brief them from scratch for each task — you just say what you need.

That's what LITIGAGENT becomes: a persistent, case-aware workspace where the attorney's only job is to direct the work.

---

## 2. What Changes (and What Doesn't)

### What changes
- **Navigation**: The case workspace (`/cases/[caseId]`) becomes the primary attorney interface. Tools are modes *within* the workspace, not separate destinations.
- **Context flow**: Case metadata (parties, court, claims, dates) is extracted from uploaded files and flows into every tool automatically.
- **Information architecture**: Attorney tools move from `/tools/discovery/*` and `/tools/litigagent/*` into a unified `/cases/[caseId]/*` hierarchy.
- **First-run experience**: "Create a case → upload files" replaces the current tools index as the attorney entry point.

### What doesn't change (yet)
- **Individual tool workflows**: Discovery wizards, objection drafter steps, chat — these stay as-is internally. We're connecting them, not redesigning them.
- **Backend APIs**: Existing endpoints (`/api/cases`, `/api/discovery`, `/api/objections`) remain. We add a context layer on top.
- **Consumer experience**: The free tools (intake, calculators, agency routing) and consumer chat are untouched.

---

## 3. The Case Workspace

### 3.1 Information Architecture

**Current** (isolated tools):
```
/tools
  ├── /tools/litigagent              → Case list
  │   └── /tools/litigagent/[caseId] → File viewer + chat drawer
  ├── /tools/discovery               → Discovery hub
  │   ├── /tools/discovery/srogs     → Wizard (standalone)
  │   ├── /tools/discovery/rfpds     → Wizard (standalone)
  │   ├── /tools/discovery/rfas      → Wizard (standalone)
  │   ├── /tools/discovery/frogs-*   → Wizard (standalone)
  │   └── /tools/discovery/objection-drafter → Wizard (standalone)
  └── (future tools, also standalone)
```

**Proposed** (case-centric workspace):
```
/cases                               → Case list (create / archive / search)
  └── /cases/[caseId]               → Case workspace (persistent shell)
        ├── /files                   → Upload & manage documents (default view)
        ├── /chat                    → Chat with the case (elevated from drawer)
        ├── /case-info               → Extracted + editable metadata
        ├── /discovery               → Discovery tool picker
        │   ├── /discovery/srogs     → Wizard (pre-populated from case)
        │   ├── /discovery/rfpds     → Wizard (pre-populated from case)
        │   ├── /discovery/rfas      → Wizard (pre-populated from case)
        │   ├── /discovery/frogs-*   → Wizard (pre-populated from case)
        │   └── /discovery/objections → Drafter (pre-populated from case)
        ├── /demand-letter           → Draft / respond to demand (future)
        ├── /analysis                → Case strengths & weaknesses (future)
        └── /timeline                → Extracted event timeline (future)
```

### 3.2 The Workspace Shell

The case workspace is a persistent layout that wraps every tool. It provides:

1. **Case header** — Case name, case number (if known), quick-access metadata. Always visible.
2. **Tool navigation** — Vertical sidebar or horizontal tab bar for switching between modes. Always visible.
3. **Tool canvas** — The active tool renders here. Full width minus sidebar.

```
┌─────────────────────────────────────────────────────┐
│  Case Header: Martinez v. Acme Corp  │  Case #BC-...│
├────────┬────────────────────────────────────────────┤
│        │                                            │
│  Files │   [ Active Tool Canvas ]                   │
│  Chat  │                                            │
│  Info  │   Currently showing: Files view            │
│  ───── │   (or Chat, or Discovery wizard,           │
│  Disc. │    or Objection drafter, etc.)             │
│  Obj.  │                                            │
│  Demand│                                            │
│  ───── │                                            │
│  Time. │                                            │
│  Anal. │                                            │
│        │                                            │
├────────┴────────────────────────────────────────────┤
│  Status bar: 12 files uploaded · 3 processing       │
└─────────────────────────────────────────────────────┘
```

**Sidebar grouping:**
- **Core**: Files, Chat, Case Info (always available)
- **Work Product**: Discovery, Objections, Demand Letter
- **Analysis**: Timeline, Case Analysis

**Sidebar behavior:**
- Icons + labels at desktop width (≥1024px)
- Icons only at medium width (768–1023px)
- Bottom tab bar on mobile (<768px) — show top 4, overflow menu for rest
- Active tool highlighted with left border accent
- Badge indicators: unread chat messages, processing files count

### 3.3 The Files View (Default Landing)

When an attorney creates a case or enters an existing one, they land on Files. This is the existing three-panel LITIGAGENT layout (file list + text editor + notes), but with two additions:

**Addition 1: Upload guidance for new cases**

Empty-state screen when no files are uploaded yet:

```
┌──────────────────────────────────────────────┐
│                                              │
│     Drop your case files here                │
│     or click to browse                       │
│                                              │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ 📄 Complaint │  │ 📄 Answer    │           │
│  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ 📄 Demand    │  │ 📄 Personnel │           │
│  │    Letter    │  │    File     │            │
│  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ 📄 Pay Stubs │  │ 📄 Contract  │           │
│  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ 📄 Emails    │  │ 📄 Discovery │           │
│  │             │  │   Requests  │            │
│  └─────────────┘  └─────────────┘            │
│                                              │
│  These suggestions help us extract case      │
│  details automatically. Upload anything —    │
│  we'll figure it out.                        │
│                                              │
└──────────────────────────────────────────────┘
```

The suggestion chips are *not* filters or requirements* — they're hints that help the attorney think about what to upload first, and they signal to the user that the system understands legal workflows. Clicking a chip opens the file browser with a helpful label but no file-type restriction.

**Addition 2: Post-upload nudge**

After the first batch of files finishes processing, a non-blocking banner appears:

```
┌──────────────────────────────────────────────┐
│  ✓ 8 files processed. We extracted case      │
│  details — review them in Case Info, or      │
│  jump straight to a task:                    │
│                                              │
│  [Chat about these files]  [Prepare discovery]│
│  [Review case info →]                        │
└──────────────────────────────────────────────┘
```

This is the "choose your own adventure" moment. The attorney decides what to do next based on where they are in the case. No forced linear flow.

---

## 4. Automatic Metadata Extraction

### 4.1 The Problem It Solves

Today, every tool asks the attorney to manually enter case information: party names, case number, court, claims, dates. This is duplicated effort across tools and slows time-to-value.

If the attorney's first action is uploading files, the system should extract this information automatically and make it available to every tool downstream.

### 4.2 What We Can Extract, By Document Type

#### From a Complaint / Petition
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Plaintiff name(s) | Caption parsing (regex + LLM) | High |
| Defendant name(s) | Caption parsing | High |
| Doe defendants (count) | Caption parsing | High |
| Case number | Caption / first page header | High |
| Court name | Caption (Superior Court of California, County of ___) | High |
| Department / judge | Caption or assignment order | Medium |
| Filing date | Clerk's stamp or text | Medium |
| Plaintiff's attorney | Attorney block (name, bar #, firm, address) | High |
| Defendant's attorney | May not appear in complaint | Low |
| Causes of action | Heading parsing ("FIRST CAUSE OF ACTION — Wrongful Termination") | High |
| Protected class(es) | NLP extraction from FEHA claims | Medium |
| Employment start/end dates | Factual allegations parsing | Medium |
| Employer name & type | Defendant identification + allegations | High |
| Key factual allegations | LLM summarization of factual sections | Medium |
| Damages sought | Prayer for relief parsing | Medium |

#### From an Answer
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Defendant's attorney | Attorney block | High |
| Affirmative defenses | Numbered defense parsing | High |
| Admitted / denied facts | Paragraph-level parsing | Medium |

#### From a Demand Letter
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Demand amount | Dollar figure extraction | High |
| Response deadline | Date extraction | High |
| Claims asserted | Section/paragraph parsing | Medium |
| Settlement posture | Tone analysis (LLM) | Low |

#### From Pay Stubs
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Employer name (legal entity) | Header extraction | High |
| Employee name | Header extraction | High |
| Pay rate (hourly/salary) | Line item parsing | High |
| Pay period | Date range extraction | High |
| Deductions | Line item parsing | Medium |
| Overtime hours/rate | Line item parsing (if present) | Medium |
| YTD earnings | Summary parsing | High |

#### From Personnel Files
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Hire date | Offer letter / application | High |
| Position / title | Offer letter / reviews | High |
| Compensation history | Offer letter / raise memos | Medium |
| Performance ratings | Review documents | Medium |
| Disciplinary actions | Write-ups / warnings | High |
| Termination date | Separation notice | High |
| Stated termination reason | Separation notice | High |

#### From Emails / Correspondence
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Key dates | Date header extraction | High |
| Participants | From/To/CC parsing | High |
| Key admissions / statements | LLM extraction | Medium |
| Timeline events | Chronological ordering | Medium |

#### From Discovery Requests (Opposing Party's)
| Field | Extraction Method | Confidence |
|-------|-------------------|------------|
| Propounding party | Caption / header | High |
| Set number | Header parsing | High |
| Request count | Numbered item counting | High |
| Discovery type | Format detection (interrogatory vs. RFP vs. RFA) | High |
| Response deadline | Service date + statutory computation | Medium |

### 4.3 Extraction Architecture

**Two-tier approach:**

**Tier 1 — Deterministic extraction (fast, cheap, runs on every file)**
- Regex patterns for case numbers, dates, dollar amounts, bar numbers
- Caption block parsing (plaintiff v. defendant structure)
- Document type classification (complaint vs. demand letter vs. pay stub) based on structural cues
- Header/footer extraction for recurring metadata

**Tier 2 — LLM-assisted extraction (slower, costs per file, runs on key documents)**
- Cause of action identification and classification to our 21 `ClaimType` enum values
- Factual allegation summarization
- Entity relationship extraction (who worked for whom, in what role)
- Timeline event extraction with date normalization

**Trigger logic:**
- Tier 1 runs automatically during file processing (extend existing `process_file()` pipeline)
- Tier 2 runs when the document is classified as a "key document" (complaint, answer, demand letter) OR when the attorney requests it
- Results stored in a new `case_metadata` table and surfaced in Case Info view

### 4.4 The Fact Store: CaseFact and CaseContext

#### The design problem with flat fields

The original CaseContext design used flat, scalar fields: `employer_name: str`, `employment_start: date`, `demand_amount: Decimal`. This is wrong for litigation. Litigation data is **temporal and mutable**:

- An employee may hold 3 positions across 2 departments over 7 years — each with different titles, supervisors, and compensation
- Claims filed in the original complaint may be dropped in a First Amended Complaint
- Demand amounts change through negotiation (initial demand → counter → revised → final)
- Trial dates get continued. Discovery cutoffs get extended. Judges get reassigned.
- New parties are added (Doe amendments). Parties are dismissed.

A flat record cannot represent this. A flat record also conflates **what we know** with **how much we trust it**. An auto-extracted filing date from OCR on a scanned complaint should not carry the same weight as a date the attorney typed in themselves.

#### CaseFact: the append-only unit of knowledge

Every piece of extracted or entered metadata is stored as a `CaseFact` — an immutable record with provenance, confidence, and lifecycle state:

```python
@dataclass(frozen=True)
class CaseFact:
    """One piece of knowledge about a case.

    Facts are append-only. They are never mutated. When information changes
    (e.g., a demand amount is revised), a new fact is created and the old
    fact's superseded_by field is set. This preserves the full history of
    what we knew and when.
    """
    id: str                          # UUID
    case_id: str
    category: FactCategory           # PARTY, EMPLOYMENT, CLAIM, DATE, FINANCIAL, COURT, ATTORNEY
    fact_type: str                   # e.g., "position_held", "claim_filed", "demand_amount"
    value: dict                      # JSON — flexible structure per fact_type (see below)
    source_file_id: str | None       # which file this was extracted from (None if manual)
    extraction_method: ExtractionMethod  # REGEX, LLM, MANUAL
    confidence: float                # 0.0–1.0 (MANUAL always 1.0)
    confirmed: bool                  # True if attorney explicitly reviewed and accepted
    superseded_by: str | None        # fact_id that replaces this one (None if current)
    effective_date: date | None      # when this fact became true in the real world
    created_at: datetime             # when we learned this fact


class FactCategory(str, Enum):
    PARTY = "party"
    EMPLOYMENT = "employment"
    CLAIM = "claim"
    DATE = "date"
    FINANCIAL = "financial"
    COURT = "court"
    ATTORNEY = "attorney"


class ExtractionMethod(str, Enum):
    REGEX = "regex"          # Tier 1 deterministic extraction
    LLM = "llm"             # Tier 2 LLM-assisted extraction
    MANUAL = "manual"        # Attorney entered or corrected
```

**Key behaviors:**

- **Append-only**: Facts are never UPDATEd. A new fact supersedes an old one. The old fact's `superseded_by` is set to the new fact's ID.
- **Confidence weighting**: `MANUAL` facts always have confidence 1.0. `LLM` facts typically 0.6–0.9. `REGEX` facts typically 0.5–0.8. When a tool needs "the employer name," the `CaseContextBuilder` picks the highest-confidence current (non-superseded) fact.
- **Confirmed vs. unconfirmed**: An attorney reviewing the Case Info view and clicking "confirm" on an auto-extracted value sets `confirmed = True` without changing anything else. This is a signal that the value is trustworthy, distinct from the attorney manually entering a different value.
- **Effective date**: When this fact became true in the real world. A promotion to "Senior Analyst" has an effective_date of the promotion date, not the date we extracted it. This enables temporal ordering of employment history.

#### Fact value schemas (the `value` dict)

Each `fact_type` has a specific schema for its `value` JSON:

```python
# PARTY facts
{"name": "Maria Martinez", "role": "plaintiff", "party_type": "individual"}
{"name": "Acme Corp", "role": "defendant", "party_type": "entity"}
{"name": "Does 1-50", "role": "defendant", "party_type": "doe", "count": 50}

# EMPLOYMENT facts — one fact per position/period
{"employer": "Acme Corp", "position": "Analyst", "department": "Finance",
 "compensation_rate": 75000, "compensation_type": "salary",
 "pay_period": "annual", "start_date": "2019-03-01", "end_date": "2021-06-15",
 "change_reason": "hired"}

{"employer": "Acme Corp", "position": "Senior Analyst", "department": "Finance",
 "compensation_rate": 95000, "compensation_type": "salary",
 "pay_period": "annual", "start_date": "2021-06-15", "end_date": "2025-11-15",
 "change_reason": "promoted"}

# CLAIM facts — one fact per claim, with lifecycle status
{"claim_type": "feha_discrimination", "status": "active",
 "protected_class": "race", "supporting_facts": "..."}

{"claim_type": "wage_theft", "status": "dropped",
 "reason": "Dropped in First Amended Complaint"}

# DATE facts — one fact per significant date
{"label": "Complaint filed", "date": "2026-01-15", "date_type": "filing"}
{"label": "Trial date", "date": "2027-03-10", "date_type": "trial"}
{"label": "Discovery cutoff", "date": "2027-01-10", "date_type": "discovery_cutoff"}

# FINANCIAL facts — one fact per demand/offer/settlement event
{"label": "Initial demand", "amount": 450000, "date": "2025-12-01"}
{"label": "Counter-offer", "amount": 125000, "date": "2026-02-15"}
{"label": "Revised demand", "amount": 350000, "date": "2026-03-01"}

# COURT facts
{"court": "Superior Court of California", "county": "Los Angeles",
 "department": "7", "judge": "Hon. Sarah Chen"}

# ATTORNEY facts
{"name": "David Kim", "bar_number": "298451", "firm": "Kim & Associates",
 "side": "plaintiff", "email": "david@kimlaw.com"}
```

This is not a fixed schema enforced by the database — it's a convention enforced by the extractors and validated by the `CaseContextBuilder`. The `value` column is a JSON blob. New fact types can be added without schema migration.

#### CaseContext: the materialized view

`CaseContext` is not stored. It is **assembled on demand** from the current (non-superseded) facts in the fact store. It is a read-only snapshot that tools consume:

```python
@dataclass(frozen=True)
class CaseContext:
    """Materialized view of the current case state.

    Assembled by CaseContextBuilder from CaseFact rows.
    Read-only. Never persisted. Rebuilt on every access.
    Tools consume this; they never write to it directly.
    """
    case_id: str
    case_name: str

    # Assembled from facts
    parties: list[PartyView]
    court: CourtView | None
    attorneys: list[AttorneyView]
    employment_history: list[EmploymentPeriodView]  # ordered by start_date
    claims: list[ClaimView]                          # includes status
    key_dates: list[DateView]                        # ordered chronologically
    financials: list[FinancialView]                  # ordered chronologically

    # Provenance summary
    fact_count: int                  # total facts for this case
    confirmed_count: int             # facts the attorney has confirmed
    extraction_sources: dict[str, list[str]]  # category → [source_file_ids]

    # Convenience accessors for the most common tool needs
    @property
    def plaintiff_names(self) -> list[str]:
        """Active plaintiff names, for variable resolution."""
        return [p.name for p in self.parties if p.role == "plaintiff"]

    @property
    def defendant_names(self) -> list[str]:
        """Active defendant names, for variable resolution."""
        return [p.name for p in self.parties if p.role == "defendant"]

    @property
    def active_claims(self) -> list[ClaimView]:
        """Claims with status 'active', for discovery suggestion."""
        return [c for c in self.claims if c.status == "active"]

    @property
    def current_demand(self) -> FinancialView | None:
        """Most recent demand/offer, for demand letter context."""
        demands = [f for f in self.financials if f.label in
                   ("Initial demand", "Revised demand", "Counter-offer")]
        return demands[-1] if demands else None

    @property
    def all_person_names(self) -> list[str]:
        """All known person names, for obfuscation seeding."""
        names = []
        for p in self.parties:
            if p.party_type == "individual":
                names.append(p.name)
        for a in self.attorneys:
            names.append(a.name)
        return names

    @property
    def all_entity_names(self) -> list[str]:
        """All known org/company names, for obfuscation seeding."""
        names = []
        for p in self.parties:
            if p.party_type == "entity":
                names.append(p.name)
        for a in self.attorneys:
            if a.firm:
                names.append(a.firm)
        for e in self.employment_history:
            names.append(e.employer)
        return list(set(names))
```

The `*View` dataclasses are simple, flat objects for rendering. They are not entities — they have no identity, no lifecycle, no behavior. They are projections of the fact store.

#### CaseContextBuilder: assembly with confidence weighting

```python
class CaseContextBuilder:
    """Assembles CaseContext from CaseFact rows.

    Resolution strategy when multiple facts exist for the same field:
    1. Only current facts (superseded_by IS NULL)
    2. Confirmed facts beat unconfirmed, regardless of confidence score
    3. Among same confirmation status, highest confidence wins
    4. Among same confidence, most recent created_at wins

    Employment and financial facts are NOT deduplicated — they accumulate
    as a history. Only facts like "case_number" or "court" that represent
    a single current value go through the resolution strategy.
    """

    def build(self, case_id: str, storage: CaseFactStorage) -> CaseContext:
        facts = storage.list_current_facts(case_id)  # WHERE superseded_by IS NULL
        return CaseContext(
            case_id=case_id,
            case_name=self._resolve_case_name(facts),
            parties=self._build_parties(facts),
            court=self._build_court(facts),
            attorneys=self._build_attorneys(facts),
            employment_history=self._build_employment(facts),
            claims=self._build_claims(facts),
            key_dates=self._build_dates(facts),
            financials=self._build_financials(facts),
            fact_count=len(facts),
            confirmed_count=sum(1 for f in facts if f.confirmed),
            extraction_sources=self._build_sources(facts),
        )
```

**Why this architecture:**

- **DRY (Hunt & Thomas)**: The authoritative representation of case metadata is the fact store. CaseContext is a derived view, not a parallel truth. There is no synchronization problem because there is only one source of truth.
- **OCP (Martin)**: Adding a new fact category (e.g., `INSURANCE` for policy limits) requires adding a new `FactCategory` enum value and a `_build_insurance()` method on the builder. No existing code changes.
- **Reversibility (Hunt & Thomas, Tip 18)**: Because facts are append-only and supersession is tracked, you can always reconstruct what the case looked like at any point in time. An attorney who says "what did we think the demand was two weeks ago?" can get an answer.
- **CaseContext is a Value Object (Evans)**: It is immutable, has no identity, and is defined entirely by its attributes. Two CaseContexts built from the same facts are equal. This makes it safe to cache, pass to tools, and use as a key for obfuscation seeding.

---

## 5. The Case Info View

### 5.1 Purpose

A structured form where the attorney can review, correct, and supplement the automatically extracted metadata. This view is always accessible from the sidebar — it's the "case at a glance" screen.

### 5.2 Layout

The Case Info view is organized into collapsible sections. Each section renders facts from the fact store. Auto-extracted facts show provenance. Everything is editable.

```
┌─────────────────────────────────────────────────────┐
│  Case Info                    7 of 23 facts confirmed│
├─────────────────────────────────────────────────────┤
│                                                     │
│  ▼ CASE IDENTIFICATION                              │
│  Case name    [ Martinez v. Acme Corp         ]     │
│  Case number  [ BC-2026-12345           ] [✓]       │
│  Filing date  [ 2026-01-15              ] [✓]       │
│               ↳ complaint.pdf · confirmed           │
│                                                     │
│  ▼ COURT                                            │
│  County       [ Los Angeles  ▾ ]                    │
│  Department   [ 7                        ] [✓]      │
│  Judge        [ Hon. Sarah Chen          ]          │
│               ↳ complaint.pdf · auto-extracted      │
│                                                     │
│  ▼ PARTIES                                          │
│  ┌─ Plaintiffs ────────────────────────────────┐    │
│  │ Maria Martinez (Individual)    [✓] [Edit]   │    │
│  │ ↳ complaint.pdf                             │    │
│  │                                    [+ Add]  │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─ Defendants ────────────────────────────────┐    │
│  │ Acme Corp (Entity)             [✓] [Edit]   │    │
│  │ John Smith (Individual)            [Edit]   │    │
│  │ Does 1-50                                   │    │
│  │ ↳ complaint.pdf                             │    │
│  │                                    [+ Add]  │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ▼ ATTORNEYS                                        │
│  ┌─ Plaintiff's Counsel ──────────────────────┐     │
│  │ David Kim · Bar #298451                    │     │
│  │ Kim & Associates                  [Edit]   │     │
│  │ ↳ complaint.pdf · confirmed       [+ Add]  │     │
│  └────────────────────────────────────────────┘     │
│  ┌─ Defendant's Counsel ──────────────────────┐     │
│  │ (not yet identified)              [+ Add]  │     │
│  └────────────────────────────────────────────┘     │
│                                                     │
│  ▼ EMPLOYMENT HISTORY                               │
│  ┌──────────────────────────────────────────────┐   │
│  │ Acme Corp                                    │   │
│  │ ┌─ 2019-03-01 to 2021-06-15 ──────────────┐ │   │
│  │ │ Analyst · Finance · $75,000/yr salary    │ │   │
│  │ │ Reason: Hired                            │ │   │
│  │ │ ↳ complaint.pdf, offer-letter.pdf [Edit] │ │   │
│  │ └─────────────────────────────────────────┘ │   │
│  │ ┌─ 2021-06-15 to 2025-11-15 ──────────────┐ │   │
│  │ │ Senior Analyst · Finance · $95,000/yr    │ │   │
│  │ │ Reason: Promoted                         │ │   │
│  │ │ ↳ complaint.pdf, pay-stubs.pdf    [Edit] │ │   │
│  │ └─────────────────────────────────────────┘ │   │
│  │ Termination: "Performance issues"           │   │
│  │ ↳ termination-letter.pdf                    │   │
│  │                           [+ Add position]  │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ▼ CLAIMS & CAUSES OF ACTION                        │
│  ┌──────────────────────────────────────────────┐   │
│  │ ● FEHA Discrimination (Race)     Active [✓]  │   │
│  │ ● FEHA Retaliation               Active [✓]  │   │
│  │ ● Wrongful Termination (Pub.Pol) Active      │   │
│  │ ○ Wage & Hour Violations         Dropped     │   │
│  │   ↳ Dropped in First Amended Complaint       │   │
│  │ ↳ complaint.pdf, fac.pdf       [+ Add claim] │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ▼ KEY DATES                                        │
│  2019-03-01  Hired                                  │
│  2021-06-15  Promoted to Senior Analyst             │
│  2025-09-10  Filed internal complaint               │
│  2025-10-01  Placed on PIP                          │
│  2025-11-15  Terminated                             │
│  2025-12-01  Initial demand: $450,000               │
│  2026-01-15  Complaint filed                        │
│  2026-02-15  Counter-offer: $125,000                │
│  2026-03-01  Revised demand: $350,000               │
│  [+ Add date]                                       │
│                                                     │
│  ▼ FINANCIALS                                       │
│  ┌──────────────────────────────────────────────┐   │
│  │ 2025-12-01  Initial demand      $450,000     │   │
│  │ 2026-02-15  Counter-offer       $125,000     │   │
│  │ 2026-03-01  Revised demand      $350,000     │   │
│  │                                 [+ Add]      │   │
│  │                                              │   │
│  │ Damages sought:                              │   │
│  │ ☑ Lost wages  ☑ Emotional distress           │   │
│  │ ☑ Punitive damages  ☑ Attorney's fees        │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 5.3 Interaction Design

**Provenance and confidence:**
- Every auto-extracted value shows its source file (clickable → navigates to Files view) and extraction method (auto-extracted / confirmed / manual)
- The `[✓]` button is a **confirm** action: the attorney marks an auto-extracted value as trustworthy without changing it. This sets `confirmed = True` on the underlying fact and boosts its weight for tools and obfuscation.
- The header shows "N of M facts confirmed" — a gentle nudge to review, not a requirement.

**Editing creates new facts:**
- Editing a value does not UPDATE the existing fact. It creates a new `CaseFact` with `extraction_method = MANUAL` and `confidence = 1.0`, and sets `superseded_by` on the old fact.
- This preserves history: if the attorney changes the case number and then realizes the original was correct, the old fact is still in the store.

**List sections (employment, claims, financials, dates) are additive:**
- `[+ Add position]`, `[+ Add claim]`, `[+ Add date]` each create a new fact. They do not replace existing facts.
- Claims have a status dropdown: Active / Dropped / Amended / Settled. Changing status creates a new claim fact superseding the old one.
- Financial events are a chronological log — each entry is its own fact. The "current demand" is the most recent one.

**Nothing is required:**
- The Case Info view has no required fields, no validation errors, no "complete your profile" gates.
- An attorney can upload files, ignore Case Info entirely, and go straight to chat or discovery. The tools work with whatever context is available — more context just means better pre-population and obfuscation.
- The data is **useful context, not definitive records**. Later pleadings, amended complaints, settlement negotiations, and court orders will change values. The fact store captures this evolution rather than pretending the first extraction is final.

---

## 6. Tool Integration: The Context Bridge

### 6.1 How Context Flows Into Tools

When the attorney navigates to a tool (e.g., clicks "Discovery" in the sidebar), the tool receives the `CaseContext` and pre-populates its first step.

**Discovery wizard — Step 1 (Case Info) becomes read-only / pre-filled:**

| Discovery field | Source in CaseContext |
|---|---|
| Case name | `case_name` |
| Case number | `case_number` |
| Court | `court_name`, `county`, `department` |
| Plaintiff name | `plaintiffs[0].name` |
| Defendant name | `defendants[0].name` |
| Plaintiff's attorney | `plaintiff_counsel[0]` |
| Party role | Inferred from user's counsel alignment |
| Filing date | `filing_date` |

**Discovery wizard — Step 2 (Claims) becomes pre-selected:**

| Discovery field | Source in CaseContext |
|---|---|
| Selected claims | `claims[].claim_type` → map to `ClaimType` enum |
| Protected class | `claims[].details` (for FEHA claims) |
| Employment dates | `employment_start`, `employment_end` |

The attorney can still modify anything — pre-population is a starting point, not a constraint.

**Objection drafter — Setup step pre-populated:**

| Objection field | Source in CaseContext |
|---|---|
| Party role | From case context |
| Case parties | For variable resolution (`{EMPLOYEE}` / `{EMPLOYER}`) |

If the case files include the opposing party's discovery requests (detected during upload), the objection drafter can offer: "We found discovery requests in `defendant_srogs_set1.pdf`. Draft objections to these?"

### 6.2 Future Tool Integration

**Demand letter generator** (future):
- Pre-populated with: parties, claims, employment details, key facts, damages sought
- Attorney selects tone (aggressive / professional / conciliatory)
- Letter references specific uploaded documents as exhibits

**Demand letter response** (future):
- Upload opposing demand letter → system extracts demands and deadline
- Pre-populated with: case context, point-by-point response framework
- Attorney directs tone and counter-offer strategy

**Case analysis** (future):
- Ingests all case context + file contents
- Produces: strengths/weaknesses by claim, evidence gap analysis, comparable case outcomes
- Interactive — attorney can challenge the analysis, ask follow-ups

**Timeline generator** (future):
- Extracts all dates from all files
- Produces chronological timeline with source attribution
- Attorney can add/remove/edit events
- Exportable for use in briefs or mediation statements

### 6.3 Cross-Tool Awareness

Tools should be aware of what other tools have produced in the same case:

- If discovery has been generated, the chat can reference it: "You previously drafted 35 special interrogatories focusing on discrimination and retaliation."
- If a demand letter exists, the discovery tool can suggest document requests that support the demand's claims.
- If objections have been drafted, the case analysis can factor in what the opposing party is seeking.

This doesn't require tight coupling — it requires a shared event/artifact log per case:

```python
@dataclass
class CaseArtifact:
    artifact_id: str
    case_id: str
    artifact_type: str        # "discovery_set", "objection_draft", "demand_letter", etc.
    tool_source: str          # "discovery/srogs", "objections", "demand-letter"
    summary: str              # "35 SROGs, Set One, focusing on FEHA discrimination"
    file_path: str | None     # generated document path
    metadata: dict            # tool-specific details
    created_at: datetime
    created_by: str           # user_id
```

---

## 7. The First-Run Experience

### 7.1 New Attorney Flow

```
[Sign in with Google/Microsoft]
         ↓
[Cases list — empty state]
  "Create your first case to get started"
  [+ New Case]
         ↓
[Name your case]
  Case name: [ Martinez v. Acme Corp    ]
  [Create]
         ↓
[Files view — empty state with upload guidance]
  (See Section 3.3 — suggested file types)
  Attorney drags in 8 files
         ↓
[Processing — real-time status indicators]
  complaint.pdf ✓ Ready — 3 causes of action detected
  pay_stubs.pdf ✓ Ready
  emails.mbox   ◌ Processing (12 messages)...
         ↓
[Post-processing nudge banner]
  "We extracted case details. Review in Case Info,
   or jump to a task."
  [Review case info]  [Chat]  [Prepare discovery]
         ↓
[Attorney's choice — no forced path]
```

### 7.2 Time to Value

**Current flow** (isolated tools):
1. Navigate to LITIGAGENT → create case → upload files → wait → chat *(~3 min)*
2. Navigate to Discovery → enter case info manually → select claims → pick requests → generate *(~8 min)*
3. Navigate to Objections → enter case info → upload/paste discovery → configure → generate *(~5 min)*
4. **Total: ~16 minutes, 3 separate tool sessions, case info entered 3 times**

**Proposed flow** (unified workspace):
1. Create case → upload files → wait *(~2 min)*
2. Review auto-extracted case info *(~1 min — mostly confirming, not typing)*
3. Click "Discovery" in sidebar → claims pre-selected, parties pre-filled → pick requests → generate *(~3 min)*
4. Click "Objections" → upload opposing discovery → generate *(~2 min)*
5. **Total: ~8 minutes, 1 session, case info entered 0 times**

**50% reduction in time-to-value. Zero redundant data entry.**

---

## 8. Navigation & Interaction Patterns

### 8.1 Sidebar Navigation (Desktop)

The sidebar is the primary navigation for the case workspace. It replaces the current "back to case list" + chat drawer toggle pattern.

**Design principles:**
- **Persistent**: Always visible. Never collapsed by default on desktop.
- **Grouped**: Core (Files, Chat, Info) | Work Product (Discovery, Objections, Demand) | Analysis (Timeline, Case Analysis). Groups separated by subtle dividers.
- **Stateful**: Active tool has left-border accent (4px, primary color). Hover shows tooltip with tool name on icon-only mode.
- **Badged**: Processing file count on Files, unread messages on Chat.
- **Width**: 200px with labels (≥1280px), 56px icon-only (1024–1279px).

### 8.2 Tool Switching

Switching tools should feel instant and safe:

- **State preservation**: If the attorney is mid-way through a discovery wizard and switches to Chat, the wizard state persists. When they switch back, they're on the same step.
- **No confirmation dialogs** for switching (state is preserved, not lost).
- **Breadcrumb in header**: Shows current location: `Martinez v. Acme Corp > Discovery > Special Interrogatories`
- **Quick-switch shortcut**: `Cmd+K` / `Ctrl+K` opens command palette for power users: "Chat", "Discovery", "Objections", "Case Info", "Files"

### 8.3 Mobile Considerations

Attorney workflows are desktop-heavy, but the workspace should degrade gracefully on tablet/mobile:

- **Tablet (768–1023px)**: Sidebar collapses to icon-only (56px). Tool canvas gets full remaining width.
- **Mobile (<768px)**: Sidebar becomes bottom tab bar with top 4 tools (Files, Chat, Info, Discovery). Overflow menu (...) for remaining tools. Individual panels stack vertically (file list → text → notes).

### 8.4 The Chat Evolution

Chat graduates from a drawer overlay to a first-class workspace mode:

**Current**: Chat drawer (450px) overlays the three-panel layout. Opens/closes via header button. Feels like an add-on.

**Proposed**: Chat is a full sidebar tool. When active, it gets the full tool canvas width. It can still reference files (clickable source badges navigate to Files view), but it's not squeezed into a narrow overlay.

**The chat also becomes the command interface.** Beyond Q&A, the attorney can issue commands in natural language:

- *"Draft 20 special interrogatories about the discrimination claim"* → System navigates to Discovery, pre-selects FEHA discrimination SROGs
- *"What's our deadline to respond to their RFAs?"* → System checks case context for service dates, computes deadline
- *"Summarize the key facts from the complaint"* → Direct answer with citations to complaint sections

This is aspirational for v2 but architecturally enabled by having chat aware of all tools and case context.

---

## 9. Data Architecture Changes

### 9.1 New Tables

```sql
-- Append-only fact store for case metadata
CREATE TABLE case_facts (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    category TEXT NOT NULL,            -- FactCategory enum: party, employment, claim, etc.
    fact_type TEXT NOT NULL,           -- e.g., "position_held", "claim_filed", "demand_amount"
    value TEXT NOT NULL,               -- JSON blob (flexible per fact_type)
    source_file_id TEXT REFERENCES case_files(id) ON DELETE SET NULL,
    extraction_method TEXT NOT NULL,   -- ExtractionMethod enum: regex, llm, manual
    confidence REAL NOT NULL DEFAULT 0.5,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by TEXT REFERENCES case_facts(id) ON DELETE SET NULL,
    effective_date TEXT,               -- ISO date: when this became true in the real world
    created_at TEXT NOT NULL
);

-- Work product artifacts generated by tools
CREATE TABLE case_artifacts (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,       -- "discovery_set", "objection_draft", etc.
    tool_source TEXT NOT NULL,         -- "discovery/srogs", "objections", etc.
    summary TEXT,
    file_path TEXT,                    -- path to generated document
    metadata TEXT,                     -- JSON blob with tool-specific details
    created_at TEXT NOT NULL,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL
);

-- Indexes: optimized for CaseContextBuilder queries
CREATE INDEX idx_case_facts_current ON case_facts(case_id, category)
    WHERE superseded_by IS NULL;                    -- the "current view" query
CREATE INDEX idx_case_facts_source ON case_facts(source_file_id)
    WHERE source_file_id IS NOT NULL;               -- "what did we extract from this file?"
CREATE INDEX idx_case_facts_type ON case_facts(case_id, fact_type);
CREATE INDEX idx_case_artifacts_case ON case_artifacts(case_id);
CREATE INDEX idx_case_artifacts_type ON case_artifacts(case_id, artifact_type);
```

**Design notes:**
- `case_facts` replaces the earlier `case_metadata` design. The key difference: `case_metadata` used `field_name`/`field_value` (key-value, scalar). `case_facts` uses `category`/`fact_type`/`value` (typed JSON, supports complex structures like employment periods with nested fields).
- No `updated_at` column. Facts are immutable. Supersession replaces mutation.
- The partial index `WHERE superseded_by IS NULL` is the critical optimization — `CaseContextBuilder` always queries current facts, and this index makes that query fast regardless of how many historical facts accumulate.
- `confirmed` is a separate column (not inside the JSON `value`) because the builder needs to sort by it efficiently.

### 9.2 CaseFactStorage

```python
class CaseFactStorage:
    """CRUD for the case_facts table. Append-only semantics."""

    def add_fact(self, fact: CaseFact) -> CaseFact:
        """Insert a new fact. Returns the fact with generated ID."""

    def supersede(self, old_fact_id: str, new_fact: CaseFact) -> CaseFact:
        """Create new_fact and set old_fact.superseded_by = new_fact.id.
        Atomic (single transaction)."""

    def confirm(self, fact_id: str) -> None:
        """Set confirmed = True on a fact. The only mutation allowed."""

    def list_current_facts(self, case_id: str, category: str | None = None) -> list[CaseFact]:
        """All facts WHERE superseded_by IS NULL, optionally filtered by category."""

    def list_all_facts(self, case_id: str, category: str | None = None) -> list[CaseFact]:
        """All facts including superseded (for history view)."""

    def list_facts_for_file(self, file_id: str) -> list[CaseFact]:
        """All facts extracted from a specific file (for re-extraction on file update)."""

    def delete_facts_for_file(self, file_id: str) -> int:
        """Remove all facts sourced from a file (when file is deleted or re-processed)."""

    def fact_count(self, case_id: str) -> tuple[int, int]:
        """Returns (total_current, confirmed_current)."""
```

### 9.3 CaseContext Assembly

`CaseContext` is assembled on-demand by `CaseContextBuilder` from `list_current_facts()`. See Section 4.4 for the builder logic and confidence-weighted resolution strategy.

**Caching**: The builder result can be cached per `case_id` with a short TTL (e.g., 30 seconds) or invalidated on fact insert/supersede. For the current scale (single user per case, low request rate), no caching is needed — assembly from 50–200 facts takes <5ms.

### 9.4 API Changes

**New endpoints:**

```
GET  /api/cases/{case_id}/context         → assembled CaseContext (JSON)
GET  /api/cases/{case_id}/facts           → list current facts (with optional ?category= filter)
GET  /api/cases/{case_id}/facts/history   → list all facts including superseded
POST /api/cases/{case_id}/facts           → add a manual fact
PUT  /api/cases/{case_id}/facts/{id}/confirm → confirm an auto-extracted fact
POST /api/cases/{case_id}/facts/{id}/supersede → supersede a fact with a new value
GET  /api/cases/{case_id}/artifacts       → list work product artifacts
POST /api/cases/{case_id}/extract         → trigger Tier 2 (LLM) extraction
```

**Modified endpoints (context bridge):**

```
POST /api/discovery/generate              → accepts optional case_id parameter
POST /api/objections/generate             → accepts optional case_id parameter
```

When `case_id` is provided, these endpoints build `CaseContext` server-side and merge it with any client-provided overrides. Existing endpoints continue to work standalone for backward compatibility — tools outside the workspace are unaffected.

### 9.5 Fact Lifecycle Examples

**File upload triggers extraction:**
```
1. Attorney uploads complaint.pdf
2. process_file() extracts text (existing pipeline)
3. Tier 1 extractors run → create CaseFacts:
   - PARTY/plaintiff: {"name": "Maria Martinez", "role": "plaintiff", ...}
     source=complaint.pdf, method=REGEX, confidence=0.85
   - COURT/court_info: {"county": "Los Angeles", "department": "7", ...}
     source=complaint.pdf, method=REGEX, confidence=0.80
   - DATE/filing: {"label": "Complaint filed", "date": "2026-01-15"}
     source=complaint.pdf, method=REGEX, confidence=0.70
4. Tier 2 extraction (if enabled for complaints) → creates more facts:
   - CLAIM/feha_discrimination: {"claim_type": "feha_discrimination", "status": "active", ...}
     source=complaint.pdf, method=LLM, confidence=0.75
   - EMPLOYMENT/position_held: {"employer": "Acme Corp", "position": "Analyst", ...}
     source=complaint.pdf, method=LLM, confidence=0.65
```

**Attorney confirms a fact:**
```
5. Attorney opens Case Info, sees "Maria Martinez" as plaintiff
6. Clicks [✓] → PUT /api/cases/{id}/facts/{fact_id}/confirm
7. Fact.confirmed = True (no new fact created — confirmation is the one allowed mutation)
```

**Attorney corrects a fact:**
```
8. Attorney sees case number "BC-2026-12345" was extracted incorrectly
9. Types the correct number "BC-2026-12346"
10. POST /api/cases/{id}/facts/{old_id}/supersede
    → Creates new fact: method=MANUAL, confidence=1.0, confirmed=True
    → Sets old_fact.superseded_by = new_fact.id
11. CaseContextBuilder now picks the new fact (MANUAL > auto-extracted)
```

**Litigation changes a fact:**
```
12. Attorney uploads First Amended Complaint (FAC)
13. Tier 2 extraction detects that "Wage & Hour" claim is no longer present
14. Creates new CLAIM fact: {"claim_type": "wage_theft", "status": "dropped",
    "reason": "Dropped in First Amended Complaint"}
    → Supersedes the original "active" wage_theft claim fact
15. CaseContext.active_claims no longer includes wage_theft
16. Discovery tool no longer suggests wage-related interrogatories
```

**Demand evolves through negotiation:**
```
17. Attorney manually adds: FINANCIAL {"label": "Initial demand", "amount": 450000}
18. Later adds: FINANCIAL {"label": "Counter-offer", "amount": 125000}
19. Later adds: FINANCIAL {"label": "Revised demand", "amount": 350000}
20. These are NOT superseding each other — they are separate events in a timeline
21. CaseContext.financials = [all three, ordered by date]
22. CaseContext.current_demand = the most recent one ($350,000)
```

---

## 10. Phasing

### Parallel Execution with PRIVACY.md

LITIGAGENTv2 and PRIVACY.md are designed to be implemented **concurrently** with no blocking dependencies between them. They share one integration point — CaseContext feeding the ObfuscationEngine — which is resolved by a thin interface, not by sequencing.

```
Week  LITIGAGENTv2                   PRIVACY.md
────  ──────────────────────────────  ──────────────────────────
 1    V2.1a (fact store + builder)    P1 (Terms + ConsentModal)
 2    V2.1b (Tier 1 extractors)      P2.1-P2.5 (ObfuscationEngine)
 3    V2.1c (fact API + context EP)   P2.6-P2.9 (integration)
 4    V2.2a (Case Info read-only)     P3 (encryption at rest)
 5    V2.2b (Case Info editable)      ─── done ───
 6    V2.2c (Tier 2 extraction)
 7    V2.3a (workspace shell)
 8    V2.3b (navigation + routing)
 9    V2.4  (discovery integration)
10    V2.5  (objection integration)
11    V2.6  (chat elevation)
12    V2.7  (demand letter)
13    V2.8  (polish + mobile)
```

**Integration seam**: P2.6 (integrate ObfuscationEngine into CaseChatService) calls `CaseContext.all_person_names` and `CaseContext.all_entity_names` for obfuscation seeding. If V2.1a is not yet complete, the engine falls back to regex+NER only (no CaseContext seeding). Once V2.1a ships, the seeding activates automatically — no code change in the privacy module. This is DIP in action: the ObfuscationEngine depends on an abstraction (the CaseContext interface), not on the fact store implementation.

---

### Phase V2.1 — Fact Store & Context Foundation

**Goal**: Build the append-only fact store, the CaseContextBuilder, and the first extractors. At the end of V2.1, uploading a complaint should automatically populate party names, case number, court, and dates in the fact store, and `GET /api/cases/{id}/context` should return an assembled CaseContext.

#### V2.1a — Fact Store & Builder (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.1a.1 | `CaseFact` dataclass + `FactCategory` + `ExtractionMethod` enums | `storage/models.py` | 5 unit | 0.3d |
| V2.1a.2 | `case_facts` + `case_artifacts` tables in schema, migration | `storage/storage.py` | 3 migration | 0.3d |
| V2.1a.3 | `CaseFactStorage` CRUD — `add_fact`, `supersede`, `confirm`, `list_current_facts`, `list_all_facts`, `list_facts_for_file`, `delete_facts_for_file`, `fact_count` | `storage/case_fact_storage.py` | 20 unit | 1.0d |
| V2.1a.4 | `CaseContext` frozen dataclass + `*View` value objects (`PartyView`, `EmploymentPeriodView`, `ClaimView`, `DateView`, `FinancialView`, `CourtView`, `AttorneyView`) | `casefile/context.py` | 5 unit | 0.3d |
| V2.1a.5 | `CaseContextBuilder` — assembles CaseContext from facts with confidence weighting, `confirmed > unconfirmed > highest confidence > most recent` resolution, employment/financial accumulation (not dedup) | `casefile/context_builder.py` | 15 unit | 1.0d |

**Gate check V2.1a**: `CaseContextBuilder` correctly assembles CaseContext from a mixed bag of facts with different categories, confidence levels, confirmed/unconfirmed status, and supersession chains. Employment periods appear as an ordered list, not a single flat entry. Superseded facts are excluded. 48 tests passing.

> **V2.1a STATUS: COMPLETE** (2026-03-15) — 48 tests passing across 5 gates (V2.1a.1–V2.1a.5).

#### V2.1b — Tier 1 Extractors & Document Classifier (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.1b.1 | `DocumentClassifier` — classifies file as complaint/answer/demand_letter/pay_stub/personnel/email/discovery/generic based on structural cues (headings, caption detection, keyword density) | `casefile/classifiers.py` | 12 unit | 0.5d |
| V2.1b.2 | `CaptionExtractor` — regex parser for California Superior Court caption blocks (plaintiff v. defendant, case number, county, department, attorney blocks) | `casefile/extractors/caption.py` | 15 unit | 0.5d |
| V2.1b.3 | `DateExtractor` — regex patterns for filing dates, employment dates, deadlines; returns `(label, date, date_type)` tuples | `casefile/extractors/dates.py` | 10 unit | 0.3d |
| V2.1b.4 | `FinancialExtractor` — regex patterns for dollar amounts, pay rates, demand amounts in context | `casefile/extractors/financial.py` | 8 unit | 0.3d |
| V2.1b.5 | `EmploymentExtractor` — regex/heuristic extraction of employer name, position, compensation from pay stubs, offer letters, and complaint allegations | `casefile/extractors/employment.py` | 10 unit | 0.5d |
| V2.1b.6 | `ExtractionOrchestrator` — runs classifier → dispatches to appropriate extractors → creates `CaseFact` objects. Integrated into existing `process_file()` pipeline as a post-extraction hook (after text extraction, before embedding) | `casefile/extraction.py`, `casefile/processing.py` | 12 integration | 0.5d |
| V2.1b.7 | Re-extraction on file delete/reprocess — `delete_facts_for_file()` called when a file is deleted or reprocessed, then extractors re-run | `casefile/processing.py` | 4 integration | 0.3d |

**Gate check V2.1b**: Upload a sample California complaint PDF. After processing completes, `list_current_facts(case_id, category="party")` returns plaintiff and defendant facts. `list_current_facts(case_id, category="court")` returns court info. `DocumentClassifier` correctly identifies the file as a complaint. 71 tests passing.

> **V2.1b STATUS: COMPLETE** (2026-03-16) — 150 tests passing across 7 gates (V2.1b.1–V2.1b.7). DocumentClassifier (24 tests), CaptionExtractor (26), DateExtractor (25), FinancialExtractor (25), EmploymentExtractor (31), ExtractionOrchestrator (15), Re-extraction (4). CaseFactStorage singleton added to deps.py. `process_file()` pipeline integrated: delete old facts → classify → extract → persist. File delete cleans up facts. Reprocess replaces facts atomically.

#### V2.1c — Context API & Seeding Interface (2 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.1c.1 | `GET /api/cases/{case_id}/context` endpoint — builds and returns CaseContext JSON | `api/casefile_routes.py` | 5 API | 0.3d |
| V2.1c.2 | `GET /api/cases/{case_id}/facts` endpoint — list current facts with optional `?category=` filter | `api/casefile_routes.py` | 5 API | 0.3d |
| V2.1c.3 | Pydantic response schemas for CaseContext and CaseFact | `api/schemas.py` | 3 unit | 0.2d |
| V2.1c.4 | `CaseContextBuilder` singleton in `deps.py`, injected into `CaseChatService` | `api/deps.py` | 2 integration | 0.2d |
| V2.1c.5 | `CaseContext.all_person_names` + `all_entity_names` properties verified for ObfuscationEngine compatibility (list of strings, deterministic order) | `casefile/context.py` | 3 unit | 0.1d |
| V2.1c.6 | `CaseChatService` uses CaseContext for richer system prompt context (party names, claims, dates injected into `casefile_system.j2`) | `casefile/chat.py`, `config/prompts/casefile_system.j2` | 5 integration | 0.5d |
| V2.1c.7 | SSE status event: `{"event": "facts_extracted", "data": {"count": N}}` after Tier 1 extraction completes | `casefile/processing.py` | 2 integration | 0.3d |

**Gate check V2.1c**: Full pipeline test — upload a complaint, wait for processing, call `GET /context`, verify CaseContext JSON includes parties, court, dates. Chat with the case and verify the system prompt includes extracted context. 25 tests passing.

> **V2.1c STATUS: COMPLETE** (2026-03-17) — 31 tests passing across 7 gates (V2.1c.1–V2.1c.7). Context API endpoint (5 tests), Facts API endpoint (6), Pydantic schemas (6), CaseContextBuilder singleton + injection (4), ObfuscationEngine name compatibility (3), CaseChatService context integration (5), SSE facts_extracted event (2). `CaseContextBuilder` singleton in deps.py injected into `CaseChatService`. `casefile_system.j2` renders parties, court, attorneys, claims, dates, employment, financials from `CaseContext`. `process_file()` broadcasts `facts_extracted` SSE event after Tier 1 extraction. `CaseContext.all_person_names`/`all_entity_names` use `dict.fromkeys()` for deterministic deduped order.

**V2.1 total: ~8 days, 144 tests**

---

### Phase V2.2 — Case Info View & Tier 2 Extraction

**Goal**: The attorney can view, confirm, edit, and supplement extracted facts. LLM-assisted extraction runs on key documents for richer metadata (claims, employment history, factual allegations).

#### V2.2a — Case Info API & Read-Only Frontend (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.2a.1 | `GET /api/cases/{case_id}/facts/history` — all facts including superseded, for history view | `api/casefile_routes.py` | 3 API | 0.2d |
| V2.2a.2 | `PUT /api/cases/{case_id}/facts/{id}/confirm` — confirm endpoint | `api/casefile_routes.py` | 3 API | 0.2d |
| V2.2a.3 | `POST /api/cases/{case_id}/facts/{id}/supersede` — supersede with new value | `api/casefile_routes.py` | 5 API | 0.3d |
| V2.2a.4 | `POST /api/cases/{case_id}/facts` — add a manual fact | `api/casefile_routes.py` | 4 API | 0.3d |
| V2.2a.5 | Frontend: `case-info.tsx` component — read-only view of CaseContext, grouped by section (parties, court, attorneys, employment, claims, dates, financials), with source attribution and confirm buttons | `frontend/components/litigagent/case-info.tsx` | — | 1.0d |
| V2.2a.6 | Frontend: `litigagent-api.ts` — `getCaseContext()`, `getCaseFacts()`, `confirmFact()` API client functions | `frontend/lib/litigagent-api.ts` | — | 0.3d |
| V2.2a.7 | Frontend: Add "Info" link in case layout header (pre-workspace shell — temporary placement until V2.3) | `frontend/components/litigagent/case-layout.tsx` | 3 E2E | 0.3d |

**Gate check V2.2a**: Attorney can navigate to Case Info from case layout. Extracted facts display with source attribution. Clicking confirm updates the fact. 18 tests passing.

> **V2.2a STATUS: COMPLETE** (2026-03-19) — 21 tests passing across 7 gates (V2.2a.1–V2.2a.7). Backend: facts history endpoint (3 tests), confirm endpoint (3), supersede endpoint (5), add manual fact endpoint (4). Frontend: `case-info.tsx` read-only panel with 7 grouped sections (parties, court, attorneys, employment, claims, dates, financials), source attribution (file name resolution from IDs), confidence badges (high/medium/low), extraction method tags, effective dates, confirm buttons (hover-reveal). `litigagent-api.ts` gains `getCaseContext()`, `listFacts()`, `confirmFact()` client functions + full TypeScript interfaces. `case-layout.tsx` header "Case Info" button toggles panel (replaces three-panel file view). 3 Playwright E2E tests: toggle open/close, facts grouped with attribution, confirm button interaction.

#### V2.2b — Editable Case Info (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.2b.1 | Frontend: inline edit mode — click edit on any fact → form fields appear, save creates superseding fact via `/supersede` endpoint | `frontend/components/litigagent/case-info.tsx` | 4 E2E | 1.0d |
| V2.2b.2 | Frontend: add new facts — `[+ Add]` buttons for each section, form creates fact via `POST /facts` | `frontend/components/litigagent/case-info.tsx` | 3 E2E | 0.5d |
| V2.2b.3 | Frontend: employment history — multi-entry UI with start/end/position/employer/compensation/reason per period, ordered by start_date | `frontend/components/litigagent/case-info.tsx` | 2 E2E | 0.5d |
| V2.2b.4 | Frontend: claims status — dropdown (Active/Dropped/Amended/Settled), status change creates superseding claim fact | `frontend/components/litigagent/case-info.tsx` | 2 E2E | 0.3d |
| V2.2b.5 | Frontend: financials — chronological log of demand/offer/settlement entries with add button | `frontend/components/litigagent/case-info.tsx` | 2 E2E | 0.3d |
| V2.2b.6 | Frontend: fact count indicator in header ("N of M confirmed") | `frontend/components/litigagent/case-info.tsx` | 1 E2E | 0.2d |

**Gate check V2.2b**: Attorney can edit any extracted value (creates superseding fact), add employment periods, change claim status, add financial events. All changes persist and reflect in CaseContext. 14 E2E tests passing.

> **V2.2b STATUS: COMPLETE** (2026-03-20) — 14 E2E tests passing across 6 gates (V2.2b.1–V2.2b.6). **V2.2b.1**: `FactEditForm` component with pre-populated inputs per value key + effective date, hover-reveal Edit button on every `FactRow`, save calls `supersedeFact()` API, cancel dismisses form. `supersedeFact()` + `addFact()` API client functions added to `litigagent-api.ts`. 4 E2E tests. **V2.2b.2**: `[+ Add]` button on each `SectionHeader`, `FactAddForm` component with `CATEGORY_TEMPLATES` per category (field templates + type selector for multi-template categories like party), creates fact via `POST /facts`. 3 E2E tests. **V2.2b.3**: `EmploymentRow` component — bordered timeline cards with employer title, position/department subtitle, formatted date range (`start → end` or `→ present`), formatted compensation (`$120,000 salary / annual`), change reason amber badge. Sorted by `start_date` ascending. Employment template expanded to 9 fields. 2 E2E tests. **V2.2b.4**: `ClaimRow` component with inline status `<select>` dropdown (Active/Dropped/Amended/Settled), color-coded per status. Changing dropdown immediately calls `supersedeFact()` with updated status value. 2 E2E tests. **V2.2b.5**: `FinancialRow` component — horizontal log entries with date column, label, formatted currency (`$500,000`), sorted chronologically. `formatCurrency()` helper. Financial template gains `date` field. 2 E2E tests. **V2.2b.6**: Header fact count indicator changed from stale context counts to live computed `facts.filter(f => f.confirmed).length of facts.length confirmed`, updates instantly on confirm/add/edit. 1 E2E test. Key files: `case-info.tsx` (863 lines added), `litigagent-api.ts` (+`addFact()`, +`supersedeFact()`), 6 new E2E spec files.

#### V2.2c — Tier 2 LLM Extraction (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.2c.1 | `Tier2Extractor` — LLM-based extraction for complaints: causes of action → `ClaimType` mapping, employment relationship, protected classes, factual allegations summary | `casefile/extractors/tier2.py` | 8 unit | 1.0d |
| V2.2c.2 | Prompt template for Tier 2 extraction — structured output (JSON tool use) requesting parties, claims, employment details, key dates | `config/prompts/extract_metadata.j2` | 2 unit | 0.3d |
| V2.2c.3 | `POST /api/cases/{case_id}/extract` endpoint — triggers Tier 2 on specified file or all key documents, creates CaseFacts from results | `api/casefile_routes.py`, `casefile/extraction.py` | 5 API | 0.5d |
| V2.2c.4 | Auto-trigger: Tier 2 runs automatically when `DocumentClassifier` identifies a file as complaint, answer, or demand letter (configurable) | `casefile/processing.py` | 3 integration | 0.3d |
| V2.2c.5 | Obfuscation integration: Tier 2 extraction uses `ObfuscationEngine` when sending file content to LLM (if P2 is complete; otherwise sends raw text) | `casefile/extractors/tier2.py` | 3 integration | 0.5d |
| V2.2c.6 | Frontend: Tier 2 extraction trigger button in Case Info ("Extract more details from [filename]") + loading state | `frontend/components/litigagent/case-info.tsx` | 2 E2E | 0.3d |

**Gate check V2.2c**: Upload a real California complaint. Tier 2 extraction produces CaseFacts for claims (mapped to ClaimType enum), employment history (multiple positions if mentioned), and protected classes. Facts appear in Case Info view. If P2 is deployed, extraction sends obfuscated text. 23 tests passing.

> **V2.2c STATUS: COMPLETE** (2026-03-22) — 49 tests passing across 6 gates (V2.2c.1–V2.2c.6). `Tier2Extractor` (Claude tool_use structured JSON output), `extract_metadata.j2` prompt template, `POST /api/cases/{case_id}/extract` endpoint, auto-trigger on complaint/answer/demand_letter classification in `process_file()`, `ObfuscationEngine` integration (sends obfuscated text when privacy module available), frontend "Extract more details from [filename]" button in Case Info with loading state. Key files: `casefile/extractors/tier2.py`, `casefile/processing.py`, `casefile_routes.py`, `case-info.tsx`. 47 backend tests + 2 E2E tests.

**V2.2 total: ~9 days, 55 tests**

---

### Phase V2.3 — Workspace Shell & Navigation

**Goal**: The unified case workspace replaces the current isolated tool navigation. All attorney tools render inside a persistent shell with sidebar navigation.

#### V2.3a — Workspace Layout (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.3a.1 | Route structure: `/cases` (case list), `/cases/[caseId]` (workspace shell with child routes) | `frontend/app/cases/`, `frontend/app/cases/[caseId]/layout.tsx` | — | 0.5d |
| V2.3a.2 | Workspace shell component: case header + sidebar + tool canvas | `frontend/components/litigagent/workspace-shell.tsx` | — | 1.0d |
| V2.3a.3 | Sidebar navigation: grouped (Core: Files/Chat/Info, Work Product: Discovery/Objections/Demand, Analysis: Timeline/Analysis), active state, badges | `frontend/components/litigagent/workspace-sidebar.tsx` | — | 0.5d |
| V2.3a.4 | Mobile responsive: sidebar → bottom tab bar at <768px, icon-only at 768–1024px | `frontend/components/litigagent/workspace-sidebar.tsx` | — | 0.5d |
| V2.3a.5 | Case header: case name, case number (if known), fact count indicator, back-to-list link | `frontend/components/litigagent/workspace-shell.tsx` | 3 E2E | 0.5d |

**Gate check V2.3a**: Case workspace renders with sidebar. Clicking sidebar items changes the URL. Mobile breakpoint shows bottom tab bar. 3 E2E tests passing.

> **V2.3a STATUS: COMPLETE** (2026-03-22) — 3 E2E tests passing across 5 gates (V2.3a.1–V2.3a.5). **V2.3a.1**: Route structure — `/cases` (case list, reuses `CaseList` component) + `/cases/[caseId]` (workspace shell layout wrapping child routes via `layout.tsx`). **V2.3a.2**: `workspace-shell.tsx` — persistent workspace chrome: case header (back link + case name), sidebar (md+), bottom tab bar (<md), tool canvas. Loads case info via `getCase()`, handles loading/error states. `case-layout.tsx` gains `showHeader` prop (default `true`) — when `false`, skips `getCase()` and shows compact toolbar instead of full header. **V2.3a.3**: `workspace-sidebar.tsx` — grouped sidebar navigation (Core: Files/Chat/Info, Work Product: Discovery/Objections/Demand, Analysis: Timeline/Analysis). 8 inline SVG icon components. `useActiveKey()` derives active nav from `usePathname()`. Disabled items at 50% opacity with "coming soon" tooltip. File count badge on Files item. **V2.3a.4**: Mobile responsive — `WorkspaceBottomBar` named export for `<768px` (Core items only, `env(safe-area-inset-bottom)`, active top accent bar, badge pills). Icon-only sidebar at `768–1024px` (`w-14`), expanded with labels at `>1024px` (`lg:w-48`). **V2.3a.5**: Case header polish — case name + description (case number proxy) with truncation, fact count indicator pill (`confirmed/total` via `getCaseContext()` in parallel, graceful `.catch(() => null)`), `data-testid` attributes for testing. Key files: `frontend/app/cases/page.tsx`, `frontend/app/cases/[caseId]/layout.tsx`, `frontend/app/cases/[caseId]/page.tsx`, `frontend/components/litigagent/workspace-shell.tsx`, `frontend/components/litigagent/workspace-sidebar.tsx`, `frontend/components/litigagent/case-layout.tsx` (modified). E2E: `workspace-header.spec.ts` (3 tests: name+description+facts display, back navigation, fact indicator hidden when 0 facts). Old `/tools/litigagent` routes remain untouched (backward compat — redirects in V2.3b.3/V2.3b.4).

#### V2.3b — Tool Canvas & State Preservation (3 days)

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.3b.1 | Tool canvas renders: Files view (existing `case-layout.tsx` three-panel), Chat (existing `chat-drawer.tsx` elevated to full panel), Case Info (existing `case-info.tsx`) as child routes | `frontend/app/cases/[caseId]/files/`, `frontend/app/cases/[caseId]/chat/`, `frontend/app/cases/[caseId]/info/` | 3 E2E | 1.0d |
| V2.3b.2 | State preservation: switching between tools does not lose in-progress state (React context or `sessionStorage` per tool per case) | `frontend/lib/workspace-context.tsx` | 3 E2E | 0.5d |
| V2.3b.3 | Migrate existing `/tools/litigagent/[caseId]` route to `/cases/[caseId]/files` with redirect for backward compatibility | `frontend/app/tools/litigagent/[caseId]/page.tsx` | 1 E2E | 0.3d |
| V2.3b.4 | Case list: migrate `/tools/litigagent` to `/cases` with redirect | `frontend/app/tools/litigagent/page.tsx`, `frontend/app/cases/page.tsx` | 1 E2E | 0.2d |
| V2.3b.5 | Tools index (`/tools`) updates: LITIGAGENT card links to `/cases` instead of `/tools/litigagent`, discovery cards note "also available from case workspace" | `frontend/app/tools/page.tsx` | — | 0.2d |
| V2.3b.6 | Breadcrumb: `Cases > Martinez v. Acme > Files` / `Cases > Martinez v. Acme > Discovery > SROGs` | `frontend/components/litigagent/workspace-shell.tsx` | — | 0.3d |
| V2.3b.7 | Command palette (`Cmd+K`): quick-switch between tools within workspace | `frontend/components/litigagent/command-palette.tsx` | 2 E2E | 0.5d |

**Gate check V2.3b**: Navigate to case workspace → Files → Chat → Info → back to Files. State is preserved. Old routes redirect. Breadcrumb updates. Command palette opens and navigates. 13 E2E tests passing.

> **V2.3b STATUS: COMPLETE** (2026-03-23) — 13 E2E tests passing across 7 gates (V2.3b.1–V2.3b.7). **V2.3b.1**: Tool canvas — Files/Chat/Info render as child routes (`/cases/[caseId]/files|chat|info`). `chat-panel.tsx` extracted from `chat-drawer.tsx` as full-panel component. `case-layout.tsx` gains `showHeader` prop (compact toolbar in workspace, full header standalone). 3 E2E tests (`workspace-navigation.spec.ts`). **V2.3b.2**: State preservation — `WorkspaceProvider` in `lib/workspace-context.tsx` wraps workspace layout. `useRef<Map>` store (no re-renders). `useToolState`/`useToolStateOptional` hooks. Files tool preserves `selectedFileId`/`notesCollapsed`; Chat tool preserves `messages`/`sessionId`/`input` (skips API reload on restore). 3 E2E tests (`workspace-state.spec.ts`). **V2.3b.3**: Legacy `/tools/litigagent/[caseId]` → server `redirect()` to `/cases/[caseId]/files`. **V2.3b.4**: Legacy `/tools/litigagent` → server `redirect()` to `/cases`. `case-list.tsx` updated to navigate to `/cases/[id]`. Combined 2 E2E tests (`workspace-redirect.spec.ts`). **V2.3b.5**: Tools index — LITIGAGENT card `href` → `/cases`, discovery cards note "Also available from the case workspace." **V2.3b.6**: Breadcrumb — `Breadcrumb` component in `workspace-shell.tsx` renders `Cases > Case Name > Tool` (chevron separators, `usePathname`-derived segments, nested segment support). Replaced back-button header. Error state uses `<Link>` instead of `router.push`. **V2.3b.7**: Command palette — `command-palette.tsx` modal. `Cmd+K`/`Ctrl+K` global listener, search filter, `↑↓` keyboard navigation, disabled items with "Coming soon", backdrop click/Esc close. Excludes current tool from list. 2 E2E tests (`command-palette.spec.ts`). Key files: `lib/workspace-context.tsx`, `components/litigagent/command-palette.tsx`, `components/litigagent/chat-panel.tsx`, `components/litigagent/workspace-shell.tsx`, `app/cases/[caseId]/{files,chat,info}/page.tsx`.

**V2.3 total: ~6 days, 16 E2E tests**

---

### Phase V2.4 — Discovery Integration

**Goal**: Discovery wizards render inside the case workspace and pre-populate from CaseContext.

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.4.1 | Case workspace routes for discovery: `/cases/[caseId]/discovery` (hub), `/cases/[caseId]/discovery/srogs`, etc. | `frontend/app/cases/[caseId]/discovery/` | 2 E2E | 0.5d |
| V2.4.2 | `DiscoveryContext` accepts optional `CaseContext` prop — auto-fills `caseInfo` (parties, court, attorney, case number) from context when provided | `frontend/lib/discovery-context.tsx` | 3 unit | 0.5d |
| V2.4.3 | Claims pre-selection: `CaseContext.active_claims` mapped to `ClaimType` values → auto-checked in Step 2 | `frontend/lib/discovery-context.tsx` | 2 unit | 0.3d |
| V2.4.4 | Variable resolution: `{EMPLOYEE}` / `{EMPLOYER}` resolved from `CaseContext.plaintiff_names[0]` / `CaseContext.defendant_names[0]` | `frontend/components/discovery/docx-wizard.tsx` | 2 unit | 0.3d |
| V2.4.5 | Party role inference: if the user's counsel matches plaintiff's counsel in CaseContext, default party_role to "plaintiff" | `frontend/lib/discovery-context.tsx` | 1 unit | 0.2d |
| V2.4.6 | `case_artifacts` table: generated discovery documents saved as artifacts (`POST /api/cases/{id}/artifacts`) | `api/casefile_routes.py`, `api/discovery_routes.py` | 4 API | 0.5d |
| V2.4.7 | Discovery hub inside workspace shows existing artifacts ("Set 1 SROGs generated Mar 10") | `frontend/app/cases/[caseId]/discovery/page.tsx` | 2 E2E | 0.5d |
| V2.4.8 | Standalone discovery routes (`/tools/discovery/*`) continue to work without CaseContext for attorneys who don't use the workspace | Verify existing tests pass | 0 new | 0.2d |

**Gate check V2.4**: Open case workspace → click Discovery → select SROGs. Step 1 is pre-filled with party names and case number from CaseContext. Step 2 has claims pre-checked. Variables resolve to real names. Generated document saved as artifact. 16 tests passing.

**V2.4 total: ~3 days, 16 tests**

> **V2.4 STATUS: COMPLETE** (2026-03-25) — 20 tests passing across 8 gates (V2.4.1–V2.4.8). **V2.4.1**: Workspace discovery routes — `/cases/[caseId]/discovery` hub + 5 sub-routes (srogs, rfpds, rfas, frogs-general, frogs-employment, objection-drafter). `discovery-workspace-wrapper.tsx` fetches CaseContext, provides to DiscoveryProvider. Sidebar navigation + breadcrumb integration. 2 E2E tests (`workspace-discovery.spec.ts`). **V2.4.2**: CaseContext auto-fill — `mapCaseContextToCaseInfo()` maps parties/court/attorneys/case_number. `DiscoveryProvider` accepts `caseContext` prop, auto-fills `caseInfo` in state initializer. 3 E2E tests (`workspace-discovery-autofill.spec.ts`). **V2.4.3**: Claims pre-selection — `mapCaseContextToClaims()` maps `CaseContext.claims[].claim_type` to `ClaimType` values via `VALID_CLAIM_VALUES` set. Auto-checked in Step 2 via `selectedClaims` state. 2 E2E tests. **V2.4.4**: Variable resolution — `request-builder.tsx` threads `caseInfo` to `HighlightedText`, calls `resolveVariables()` before rendering. `{EMPLOYEE}`/`{EMPLOYER}` resolve to actual party names. `docx-wizard.tsx` passes `state.caseInfo` to `RequestBuilder`. 1 E2E test. **V2.4.5**: Party role inference — `inferPartyRole()` matches `useAuth()` user email against CaseContext attorneys (case-insensitive), infers role from `side` field. `discovery-workspace-wrapper.tsx` passes `user?.email` to provider. 1 E2E test. **V2.4.6**: Artifact tracking — `ArtifactType` enum + `CaseArtifact` dataclass in models.py. `CaseStorage` CRUD (create/list/get/delete). `ArtifactResponse`/`ArtifactListResponse` schemas. 3 API endpoints (POST/GET/DELETE). `_save_discovery_artifact()` best-effort helper in discovery_routes.py. `case_id` field on `GenerateOptions`/`DiscoveryGenerateRequest`. Frontend: `ArtifactInfo` type + `listArtifacts()`/`deleteArtifact()` API client. 9 backend tests (`test_case_artifacts.py`). **V2.4.7**: Discovery hub artifacts — `page.tsx` fetches artifacts via `listArtifacts()`, displays "Generated Documents" section with `TOOL_LABELS` mapping, `formatDate()`, "Open tool" links, delete buttons. 2 E2E tests (`workspace-discovery-artifacts.spec.ts`). **V2.4.8**: Standalone compatibility — verified all 65 standalone discovery E2E tests pass. No code changes needed. Key files: `frontend/lib/discovery-context.tsx`, `frontend/components/discovery/request-builder.tsx`, `frontend/components/discovery/docx-wizard.tsx`, `frontend/components/discovery/frog-wizard.tsx`, `frontend/app/cases/[caseId]/discovery/` (7 pages), `frontend/lib/litigagent-api.ts`, `src/employee_help/storage/models.py`, `src/employee_help/storage/case_storage.py`, `src/employee_help/api/casefile_routes.py`, `src/employee_help/api/discovery_routes.py`.

---

### Phase V2.5 — Objection Integration

**Goal**: Objection drafter renders inside the workspace and pre-populates from CaseContext.

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.5.1 | Case workspace route: `/cases/[caseId]/objections` | `frontend/app/cases/[caseId]/objections/page.tsx` | 1 E2E | 0.3d |
| V2.5.2 | `ObjectionContext` accepts optional `CaseContext` — pre-fills party role | `frontend/lib/objection-context.tsx` | 2 unit | 0.3d |
| V2.5.3 | "Discovery requests in your files" detection: if CaseContext contains `fact_type="discovery_request"` facts (from uploaded opposing discovery), offer "Draft objections to [filename]?" | `frontend/app/cases/[caseId]/objections/page.tsx` | 2 E2E | 0.5d |
| V2.5.4 | Objection results saved as `CaseArtifact` | `api/objection_routes.py` | 2 API | 0.3d |
| V2.5.5 | Standalone objection route continues to work | Verify existing tests pass | 0 new | 0.1d |

**Gate check V2.5**: Objection drafter inside workspace pre-selects party role. If opposing discovery exists in files, it offers to draft objections. Results saved as artifact. 7 tests passing.

**V2.5 total: ~1.5 days, 7 tests**

> **V2.5 STATUS: COMPLETE** (2026-03-25) — 7 tests passing across 5 gates (V2.5.1–V2.5.5). **V2.5.1**: Workspace objections route — `/cases/[caseId]/objections` renders `ObjectionDrafter` inside workspace shell with `ObjectionDrafterProvider`. 1 E2E test. **V2.5.2**: CaseContext party role inference — `ObjectionDrafterProvider` accepts `caseContext` prop, `inferPartyRole()` maps CaseContext parties to objection drafter `partyRole` state. 2 unit tests. **V2.5.3**: Discovery request detection banner — `DiscoveryRequestDetector` scans `listFacts()` for `fact_type="discovery_request"`, shows "Draft objections to [filename]?" buttons, loads file text via `getFile()` and dispatches `SET_RAW_TEXT`. 2 E2E tests. **V2.5.4**: Artifact tracking — `_save_objection_artifact()` in `objection_routes.py` creates `CaseArtifact` with request/objection counts on generate. 2 API tests. **V2.5.5**: Standalone compatibility — verified existing objection drafter E2E tests pass unchanged. Key files: `frontend/app/cases/[caseId]/objections/page.tsx`, `frontend/lib/objection-context.tsx`, `src/employee_help/api/objection_routes.py`.

---

### Phase V2.6 — Chat Elevation

**Goal**: Chat moves from a drawer overlay to a full workspace mode. It gains awareness of CaseArtifacts and richer CaseContext.

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.6.1 | `/cases/[caseId]/chat` renders the chat interface at full canvas width (not 450px drawer) | `frontend/app/cases/[caseId]/chat/page.tsx` | 2 E2E | 0.5d |
| V2.6.2 | Chat system prompt includes CaseContext summary (parties, claims, key dates) and CaseArtifact list ("you previously generated 35 SROGs...") | `casefile/chat.py`, `config/prompts/casefile_system.j2` | 3 integration | 0.5d |
| V2.6.3 | Chat-to-file navigation: source badges for case files still navigate to Files view via workspace routing (not drawer close) | `frontend/app/cases/[caseId]/chat/page.tsx` | 1 E2E | 0.3d |
| V2.6.4 | Suggested questions use CaseContext: if claims are known, suggest questions about those specific claims; if employment history exists, suggest timeline questions | `frontend/app/cases/[caseId]/chat/page.tsx` | 2 E2E | 0.3d |
| V2.6.5 | Command palette integration: "Chat" in palette navigates to chat view | Covered by V2.3b.7 | — | 0.1d |

**Gate check V2.6**: Chat renders full-width in workspace. System prompt references extracted context and artifacts. Suggested questions are context-aware. Source badges navigate to files. 8 E2E + integration tests passing.

**V2.6 total: ~1.7 days, 8 tests**

> **V2.6 STATUS: COMPLETE** (2026-03-25) — 8 tests passing across 5 gates (V2.6.1–V2.6.5). **V2.6.1**: Full-canvas chat — `/cases/[caseId]/chat` renders `ChatPanel` inline within workspace shell (not 450px fixed drawer). Verified not fixed-positioned, width >600px, sidebar active state. 2 E2E tests (`workspace-chat.spec.ts`). **V2.6.2**: CaseContext + CaseArtifact in system prompt — `get_case_artifacts()` method on `CaseChatService` fetches artifacts from `CaseStorage`. `build_case_system_prompt()` accepts `case_artifacts` param. `casefile_system.j2` gains conditional `{% if case_artifacts %}` "Prior Work Products" section listing summaries with dates and instruction to reference existing work. Both `generate_stream()` and `generate_stream_multiturn()` fetch and pass artifacts. 3 integration tests (`test_case_chat_context_integration.py`). **V2.6.3**: Chat-to-file navigation — case file source badges changed from `<span>` to `<button>` with `handleNavigateToFile()` callback. Sets `files` tool state `selectedFileId` via workspace context and navigates to `/cases/${caseId}/files` via `router.push()`. 1 E2E test. **V2.6.4**: Context-aware suggestions — `computeSuggestions(files, caseContext?)` extended with optional `CaseContextInfo`. Active claims → claim-specific questions; multiple claims → prioritization suggestion; employment history → timeline question; key dates → deadline/SOL question. `ChatPanel` fetches `getCaseContext()` on mount. 2 E2E tests. **V2.6.5**: Command palette "Chat" — already registered in `command-palette.tsx` (covered by V2.3b.7). Key files: `frontend/components/litigagent/chat-panel.tsx`, `frontend/components/litigagent/chat-drawer.tsx`, `src/employee_help/casefile/chat.py`, `config/prompts/casefile_system.j2`, `frontend/e2e/workspace-chat.spec.ts`.

---

### Phase V2.7 — Demand Letter (New Tool)

**Goal**: Draft and respond to demand letters using case context and file contents.

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.7.1 | `DemandLetterService` — LLM-based demand letter generation from CaseContext + selected file content. Tone selector (aggressive/professional/conciliatory). Structured output with sections (introduction, facts, legal basis, damages, demand, deadline) | `casefile/demand.py` | 10 unit | 1.5d |
| V2.7.2 | `POST /api/cases/{case_id}/demand` — generate demand letter (SSE streaming), saves as CaseArtifact + creates FINANCIAL fact with demand amount | `api/casefile_routes.py` | 5 API | 0.5d |
| V2.7.3 | Demand letter response mode: upload opposing demand letter → system extracts demands → attorney drafts point-by-point response | `casefile/demand.py` | 5 unit | 1.0d |
| V2.7.4 | Frontend: `/cases/[caseId]/demand-letter` — tone selector, file selector (which documents to reference), streaming output, export to DOCX | `frontend/app/cases/[caseId]/demand-letter/page.tsx` | 4 E2E | 1.5d |
| V2.7.5 | Obfuscation integration: demand letter generation uses ObfuscationEngine | `casefile/demand.py` | 2 integration | 0.3d |

**Gate check V2.7**: Generate a demand letter from case context with aggressive tone. Letter references uploaded documents by name, cites relevant statutes, and states a demand amount. Amount appears as FINANCIAL fact in case info. Export works. 26 tests passing.

**V2.7 total: ~4.8 days, 26 tests**

---

### Phase V2.8 — Polish & Mobile

**Goal**: Responsive workspace, refined empty states, performance, onboarding.

| Gate | Task | Files | Tests | Est. |
|------|------|-------|-------|------|
| V2.8.1 | Mobile workspace: bottom tab bar with top 4 tools + overflow menu, panels stack vertically on narrow screens | Various | 3 E2E | 1.0d |
| V2.8.2 | File upload empty state (Section 3.3): suggested file type chips, "we'll figure it out" reassurance | `frontend/components/litigagent/file-panel.tsx` | 1 E2E | 0.5d |
| V2.8.3 | Post-upload nudge: non-blocking banner after first batch processing ("8 files processed. Review case info or jump to a task") | `frontend/components/litigagent/case-layout.tsx` | 1 E2E | 0.3d |
| V2.8.4 | Lazy-load tool modules: discovery wizard, objection drafter, demand letter loaded on navigation (not on workspace mount) via `dynamic()` | Various | — | 0.5d |
| V2.8.5 | Performance: CaseContext caching (30s TTL, invalidated on fact change) to avoid rebuilding on every request | `casefile/context_builder.py`, `api/deps.py` | 2 unit | 0.3d |
| V2.8.6 | Remove deprecated routes: clean up `/tools/litigagent` redirects after grace period | Various | — | 0.2d |

**Gate check V2.8**: Workspace works on 375px-wide viewport. Empty case shows file upload guidance. Post-upload banner appears. Tools lazy-load. 8 tests passing.

**V2.8 total: ~2.8 days, 8 tests**

---

### Phase Summary

| Phase | Focus | Days | Tests | Depends On |
|-------|-------|------|-------|------------|
| V2.1 | Fact store, extractors, context API | 8 | 144 | — (runs parallel with P1, P2) |
| V2.2 | Case Info view, editing, Tier 2 extraction | 9 | 55 | V2.1 |
| V2.3 | Workspace shell, navigation, routing | 6 | 16 | V2.1 (for Case Info sidebar link) |
| V2.4 | Discovery integration | 3 | 16 | V2.3 (workspace routes), V2.1 (CaseContext) |
| V2.5 | Objection integration | 1.5 | 7 | V2.3, V2.1 |
| V2.6 | Chat elevation | 1.7 | 8 | V2.3, V2.1 |
| V2.7 | Demand letter | 4.8 | 26 | V2.3, V2.1, P2 (obfuscation) |
| V2.8 | Polish & mobile | 2.8 | 8 | V2.3 |
| **Total** | | **~37 days** | **~280 tests** | |

**Critical path**: V2.1 → V2.2 → V2.3 → V2.4/V2.5/V2.6 (parallel) → V2.7 → V2.8

V2.2 and V2.3 can run in parallel (different files — V2.2 is backend API + Case Info component, V2.3 is workspace shell + routing). V2.4, V2.5, and V2.6 are independent and can run in parallel after V2.3.

---

## 11. Success Metrics

| Metric | Current (Isolated Tools) | Target (Workspace) |
|--------|--------------------------|---------------------|
| Time to first work product | ~16 min | <8 min |
| Case info re-entry across tools | 3x | 0x |
| Tools used per case session | 1.2 avg | 2.5+ avg |
| Session duration | 8 min avg | 20+ min avg |
| Return rate (next-day) | Unknown | >40% |
| Files uploaded per case | 3 avg | 8+ avg |

### North Star

**The attorney should never have to tell the system something it could have learned from the files.**

---

## 12. Design Principles

1. **Files first, tools second.** The case files are the source of truth. Tools consume context from files, not from manual forms.

2. **Extract, don't interrogate.** Pre-populate everything possible. Ask the attorney to *confirm*, not *enter*.

3. **No dead ends.** Every screen should offer a clear next action. Post-upload → review or chat. Post-discovery → export or draft more. Post-chat → follow the citation.

4. **State survives navigation.** Switching between tools never loses work. The workspace remembers where you were.

5. **Progressive disclosure.** Show the most-used tools prominently. Tuck future/advanced tools in the sidebar without hiding them. Don't overwhelm on first visit.

6. **The Junior Associate knows the case.** Every tool interaction should feel like the system already read the files. No cold starts within a case.

---

## 13. Privacy & Confidentiality Architecture

> **Canonical reference**: [PRIVACY.md](./PRIVACY.md) — the full implementation plan for entity obfuscation, informed consent, and encryption at rest.

LITIGAGENTv2 is the system that handles privileged attorney work product. Privacy is not a bolt-on — it is woven into the architecture. This section describes how the workspace integrates with the privacy framework and what the attorney experiences.

### 13.1 The Core Architecture

The case workspace processes data through two distinct channels:

**Local channel (no third-party involvement):**
- File extraction (PDF, DOCX, Excel, email, images, OCR)
- Text chunking and embedding (sentence-transformers, local CPU)
- Vector and full-text search (LanceDB, embedded)
- Case metadata extraction (Tier 1 regex, runs in `process_file()`)
- Document generation (discovery DOCX/PDF via docxtpl/PyPDFForm)
- All SQLite storage (case files, notes, metadata, artifacts)

**Anthropic API channel (obfuscated):**
- Case chat (query + retrieved case chunks + notes + conversation history)
- Objection analysis (discovery request text)
- Tier 2 metadata extraction (LLM-assisted, for key documents like complaints)

Every API call passes through the `ObfuscationEngine` (see [PRIVACY.md §4](./PRIVACY.md#4-phase-p2-obfuscation-engine)), which replaces identifying entities (party names, attorneys, companies, emails, phones, case numbers) with generic placeholders before transmission and restores them on response.

### 13.2 CaseContext Feeds Obfuscation

The `CaseContext` object (Section 4.4) serves double duty:

1. **Pre-populates tools** — party names, claims, dates flow into Discovery, Objections, and other tools (Section 6)
2. **Seeds the obfuscation engine** — known parties from case metadata are matched with 100% precision during entity replacement

This creates a virtuous cycle: the more facts the attorney confirms in the Case Info view, the more accurate the obfuscation becomes. The first file upload triggers Tier 1 extraction → facts stored → CaseContext assembled → all subsequent API calls benefit from high-precision entity seeding.

```
┌─────────────────────────────────────────────────────────┐
│  Case Workspace                                         │
│                                                         │
│  Upload files ──→ Tier 1 extraction ──→ CaseFact store  │
│                                              │          │
│                                     CaseContextBuilder  │
│                                              │          │
│                                        CaseContext      │
│                                         │        │      │
│                                  ┌──────┘        └───┐  │
│                                  │                   │  │
│                             Pre-populates         Seeds │
│                             tool forms         obfusc. │
│                                  │                   │  │
│                                  ▼                   ▼  │
│                             Discovery        ObfuscationEngine
│                             Objections             │    │
│                             Demand Letter          │    │
│                                  │          ┌──────┘    │
│                                  ▼          ▼           │
│                             Anthropic API (obfuscated)  │
└─────────────────────────────────────────────────────────┘
```

**The fact store design strengthens obfuscation**: Because CaseContext is assembled from confirmed facts (with `confirmed > unconfirmed` priority), and because attorneys can add facts manually (with confidence 1.0), the entity seed list improves over time. An attorney who confirms party names in Case Info guarantees those names will be caught by obfuscation — no NER uncertainty.

### 13.3 What the Attorney Sees

The privacy framework is communicated through a small number of **existing, evergreen surfaces** — not through a proliferation of modals, banners, or interstitials. The principle: inform once, link to canonical pages, don't interrupt the workflow.

| Surface | What It Says | When | New or Existing? |
|---|---|---|---|
| **Attorney ConsentModal** | Updated 5 bullets covering AI data processing, obfuscation, local storage, professional responsibility, and Terms acceptance | First time attorney mode is used (once, stored in localStorage with version check) | **Existing** — content updated |
| **Terms of Use** (`/terms`) | Section 11: AI Processing of Case Materials — safeguards, limitations, assumption of responsibility, limitation of liability, indemnification | Always available, linked from modal and footer | **Existing** — content added |
| **Privacy Policy** (`/privacy`) | Case File Data Processing section — what is collected, what goes to Anthropic, what stays local, retention policy | Always available, linked from modal and footer | **Existing** — content added |
| **Disclaimer footer** | Unchanged — links to Terms and Privacy | Every page | **Existing** — no changes |
| **Chat input hint** | "Identifying info is obfuscated before AI processing. [Terms →]" | Below case chat input, always visible | **New** — one line of small inline text |

**What we do NOT add:**
- No per-case consent modal or banner
- No new modal components
- No new banner components
- No new pages
- No dismissible warnings or toasts about privacy

The ConsentModal already exists and already gates attorney tool access. We update its text. The Terms and Privacy pages already exist and are already linked from the footer and modal. We add content to them. One small inline hint below the chat input is the only new UI element.

### 13.4 Phasing Alignment

The privacy phases from [PRIVACY.md §7](./PRIVACY.md#7-implementation-schedule) map to the LITIGAGENTv2 phases. See Section 10 for the full parallel execution timeline.

| Privacy Phase | LITIGAGENTv2 Phase | Dependency |
|---|---|---|
| **P1** (Informed Consent & Terms) | Runs **in parallel** with V2.1a (different files entirely — P1 is frontend, V2.1a is backend) | None |
| **P2** (Obfuscation Engine) | **COMPLETE** (2026-03-15). 289 tests, all 4 gate checks passed. CaseChatService + ObjectionAnalyzer integrated. Currently uses regex+NER; will benefit from CaseContext seeding when V2.1a is deployed. | Soft dependency on V2.1a for CaseContext seeding — graceful degradation (regex+NER only) until V2.1a is deployed |
| **P3** (Encryption at Rest) | Runs **in parallel** with V2.2a. Operates at storage layer, orthogonal to fact store or workspace UI. | None |

**The integration seam**: `ObfuscationEngine.seed_from_case_context()` calls `CaseContext.all_person_names` and `CaseContext.all_entity_names`. These are properties on CaseContext (Section 4.4) that return simple `list[str]`. The ObfuscationEngine depends on this interface, not on the fact store. If CaseContext is not yet available, the engine skips seeding and uses regex+NER only. This is DIP (Martin): both modules depend on an abstraction, neither depends on the other's implementation.

### 13.5 Liability Protection Strategy

See [PRIVACY.md Appendix B.4](./PRIVACY.md#b4-contractual-terms-allocation-of-risk) for the full contractual terms. In summary:

- The attorney acknowledges they are exercising independent professional judgment
- The attorney accepts responsibility for client consent where required
- The attorney accepts responsibility for supervising all AI output
- We are not liable for confidentiality-related claims arising from use of the Service
- The attorney agrees to indemnify us against such claims
- These terms are accepted via the ConsentModal (which links to Terms of Use) and reinforced by the Terms of Use Section 11

The tone is: *we built a system that takes reasonable care, we are transparent about how it works and where it falls short, and the professional responsibility for using it in a client representation belongs to the attorney.* This is the same posture adopted by every enterprise legal technology vendor (Relativity, Everlaw, CoCounsel).

---

## 14. Relationship to LITIGAGENT v1 and PRIVACY.md

[LITIGAGENT.md](./LITIGAGENT.md) defined the foundation: file extraction, three-panel layout, case-scoped chat, and the vision for workflow integration (Section 11). LITIGAGENTv2 doesn't replace that vision — it executes it.

**What v1 built (Phases L1–L3):**
- File extraction pipeline (7 extractors, OCR, background processing)
- Three-panel UI (file list, text editor, notes)
- Case-scoped embedding + dual-context retrieval
- Multi-turn chat with citation linking
- SSE streaming + session persistence

**What v2 adds:**
- Automatic metadata extraction (the intelligence layer on top of raw text extraction)
- CaseContext as the shared data contract between tools
- Unified workspace navigation (sidebar + tool canvas)
- Pre-population bridge to existing Discovery and Objection tools
- Case artifact tracking (what has been produced)
- Chat elevated from overlay to primary workspace mode
- New tools (demand letter, case analysis, timeline) enabled by the context layer

**v1 made it possible to upload files and chat about them. v2 makes those files the foundation for everything an attorney does on a case.**

### Relationship to PRIVACY.md

[PRIVACY.md](./PRIVACY.md) defines the data protection layer that runs underneath the workspace. The two documents are designed to be read together:

- **LITIGAGENTv2** describes *what the attorney does* — uploads files, extracts metadata, uses tools, generates work product
- **PRIVACY.md** describes *how data is protected while the attorney does it* — obfuscation, encryption, consent, liability terms

The CaseContext object (Section 4.4 here) is the architectural bridge: it feeds both tool pre-population (LITIGAGENTv2 concern) and obfuscation seeding (PRIVACY.md concern). Neither document should be modified without checking alignment with the other.

---

## 15. Open Questions

1. **Multi-party cases**: How does `CaseContext` handle cases with 5+ defendants, cross-complaints, or third-party claims? The data model supports lists, but the UI needs to handle complexity gracefully.

2. **Case sharing**: When organizations (Phase A4) are implemented, how does shared case access work? Can multiple attorneys work the same case simultaneously? Real-time collaboration is likely out of scope, but sequential access with conflict detection may be needed.

3. **File versioning**: If the attorney uploads an amended complaint, should the system detect it as an update to the original and re-extract metadata? Or treat it as a new file?

4. **Extraction accuracy**: What's the acceptable error rate for Tier 1 (regex) extraction? If it's wrong 20% of the time, does pre-population help or hurt? Need to test with real complaints.

5. **Cost model**: Tier 2 (LLM) extraction adds per-case cost. At what scale does this become a pricing concern? Should Tier 2 be opt-in or automatic for key documents?

6. **Offline / slow connection**: Some attorneys work from courtrooms or rural areas with poor connectivity. How does the workspace handle large file uploads over slow connections? Resumable uploads?

7. **Tool sequencing guidance**: Should the workspace suggest what to do next based on case stage? e.g., "You have a complaint but no answer — consider drafting discovery" vs. "Discovery responses are due in 15 days." This edges toward case management, which may be scope creep.
