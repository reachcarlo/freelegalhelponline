# Discovery Bank Redesign — Role-Aware, Variable-Driven, Comprehensive

> **Status**: Phases D.1–D.5 COMPLETE (2026-03-07). All gates passed.
> **Date**: 2026-03-07
> **Scope**: SROGs, RFPDs, RFAs request banks + API + frontend + claim mapping
> **Prerequisite**: Existing discovery tools (Phases 5A–5G) fully implemented and tested
> **Reference**: Learning materials at `learning/market research/discovery/requests/`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Gap Analysis](#2-gap-analysis)
3. [Architectural Decisions](#3-architectural-decisions)
4. [Variable Substitution System](#4-variable-substitution-system)
5. [Phase D.1 — Model Extension and Variable Resolver](#5-phase-d1--model-extension-and-variable-resolver)
6. [Phase D.2 — Expand Request Banks](#6-phase-d2--expand-request-banks)
7. [Phase D.3 — API and Claim Mapping Integration](#7-phase-d3--api-and-claim-mapping-integration)
8. [Phase D.4 — Frontend Integration](#8-phase-d4--frontend-integration)
9. [Phase D.5 — Documentation and Validation](#9-phase-d5--documentation-and-validation)
10. [Request Bank Inventory](#10-request-bank-inventory)
11. [Summary](#11-summary)

---

## 1. Problem Statement

The current discovery tool request banks have five critical gaps:

1. **Plaintiff-only**: All 89 requests (35 SROGs, 28 RFPDs, 26 RFAs) are written from the plaintiff's perspective. Zero defendant-side discovery exists, excluding ~50% of the attorney market.

2. **No role-based filtering**: `GET /api/discovery/banks/{tool}` returns the entire bank regardless of `party_role`. The suggest endpoint accepts `party_role` but `claim_mapping.py` ignores it entirely.

3. **No variable substitution**: Requests use static terms ("EMPLOYEE", "EMPLOYER") without adapting to party context. A defendant propounding discovery sees plaintiff-framed language.

4. **Missing categories**: No coverage for contention interrogatories, ESI, social media, medical/emotional distress, mitigation of damages, prior employment history, accommodation/interactive process, or recordings.

5. **Inflated documentation**: FUNCTIONALITY.md claims "300+ SROGs", "250+ RFPDs", "200+ RFAs" (750+ total). Actual count is 89.

---

## 2. Gap Analysis

### Current vs. Target Request Counts

| Tool | Current | Target (Plaintiff) | Target (Defendant) | Target (Shared) | Total Target |
|------|---------|--------------------|--------------------|------------------|-------------|
| SROGs | 35 | 30–35 | 20–25 | 5–10 | ~65 |
| RFPDs | 28 | 30–35 | 18–22 | 3–5 | ~58 |
| RFAs | 26 | 30–35 | 22–27 | 3–5 | ~62 |
| **Total** | **89** | **90–105** | **60–74** | **11–20** | **~185** |

### Current vs. Target Category Counts

| Tool | Current Categories | New Plaintiff Categories | New Defendant Categories | Total Target |
|------|-------------------|-------------------------|--------------------------|-------------|
| SROGs | 8 | 3 (contention, accommodation, communications) | 5 (factual basis, emotional distress, mitigation, prior employment, social media/recordings) | 16 |
| RFPDs | 14 | 3 (ESI, litigation hold, accommodation docs) | 7 (medical records, financial records, job search docs, prior employment, personal records, social media docs, govt agency docs) | 24 |
| RFAs | 6 | 4 (discrimination, comparators, damages, accommodation) | 7 (performance, policies compliance, legitimate reasons, damages limitations, mitigation, prior claims, direct evidence) | 17 |

### Missing Request Types by Side

**Plaintiff-side gaps** (requests the playbook has that we don't):
- Contention interrogatories targeting employer's affirmative defenses
- Accommodation/interactive process requests (FEHA disability cases)
- ESI in native format with metadata
- Litigation hold notices
- Decision-maker personnel files
- Prior complaints about alleged harasser (5–10 year lookback)
- Communications between decision-maker and others about employee

**Defendant-side gaps** (entire side is missing):
- Factual basis for plaintiff's claims ("State ALL FACTS upon which you base...")
- Emotional distress symptoms, medical providers, medications, prior conditions
- Mitigation efforts — job applications, income sources, declined offers
- Prior employment history (10-year lookback), prior lawsuits/charges
- Social media accounts, recordings made during employment
- Performance deficiencies, warnings, handbook acknowledgments
- Damages limitations — no medical treatment, pre-existing conditions
- Lack of direct evidence admissions

---

## 3. Architectural Decisions

### AD-1: Python over YAML for request banks

**Decision**: Keep request banks as Python frozen dataclasses in `.py` files.

**Rationale**: YAML would require a loader layer, a validation layer, and a deserialization step — all accidental complexity. The banks are small (~185 items), change infrequently, and benefit from Python's type checking, IDE navigation, and import system. No new dependency, no new failure mode.

### AD-2: Extend DiscoveryRequest, don't create RequestTemplate

**Decision**: Add three fields to `DiscoveryRequest` with backwards-compatible defaults. Do not create a separate `RequestTemplate` class.

**Rationale**: The existing class has 7 fields. Adding `applicable_roles` and `applicable_claims` makes 9. A separate template-to-instance conversion layer adds indirection without adding insight. The bank IS the template; the resolved request IS what the user sees. One class, two states.

New fields:
```python
applicable_roles: tuple[str, ...] = ("plaintiff", "defendant")  # default: both
applicable_claims: tuple[str, ...] = ()  # empty = all claims (no gate)
```

All existing requests get default values, so all existing tests pass without modification.

### AD-3: Variable resolution happens server-side

**Decision**: Build a pure-function resolver that substitutes template variables using `CaseInfo`. Resolution happens at API response time (bank endpoint) and generation time (DOCX builder).

**Rationale**: The resolver is a pure function — easy to test, no side effects, single source of truth. Duplicating this logic in TypeScript would violate DRY on knowledge. The frontend receives resolved text and renders it directly.

### AD-4: One file per tool, filtered by role

**Decision**: Keep `srogs.py`, `rfpds.py`, `rfas.py` as single files containing ALL requests (plaintiff + defendant + shared). Role filtering happens via getter functions.

**Rationale**: Role is a filter on the data, not an organizational axis. Splitting by role would duplicate categories and complicate imports. One file per tool keeps the knowledge in one place.

### AD-5: Backwards-compatible defaults for all new fields

**Decision**: Every new field gets a default that preserves existing behavior. Phase D.1 introduces zero behavioral change.

**Rationale**: The 49 E2E tests and 170+ backend discovery tests continue passing throughout D.1. Breaking changes are deferred to D.3 where API behavior changes are explicitly tested.

---

## 4. Variable Substitution System

### Variable Registry

Template variables appear in request text as `{VARIABLE_NAME}`. The resolver maps each variable using `CaseInfo` context.

| Variable | Description | Plaintiff Propounding | Defendant Propounding |
|----------|-------------|----------------------|----------------------|
| `{PROPOUNDING_PARTY}` | Name of the party serving discovery | First plaintiff name | First defendant name |
| `{RESPONDING_PARTY}` | Name of the party receiving discovery | First defendant name | First plaintiff name |
| `{PROPOUNDING_DESIGNATION}` | Role label of propounding party | "Plaintiff" | "Defendant" |
| `{RESPONDING_DESIGNATION}` | Role label of responding party | "Defendant" | "Plaintiff" |
| `{EMPLOYEE}` | The employee (always the plaintiff) | First plaintiff name | First plaintiff name |
| `{EMPLOYER}` | The employer (always the defendant) | First defendant name | First defendant name |

### How It Works

1. Request template text uses variables: `"State whether {RESPONDING_PARTY} provided {EMPLOYEE} with a copy of the employee handbook."`
2. When the API returns bank items with a `party_role` and case context, the resolver substitutes variables.
3. Unknown variables pass through unchanged (graceful fallback — no crashes).
4. The DOCX builder receives fully resolved text and formats it. The builder is a humble object that does not perform substitution.

### Backwards Compatibility

Existing requests use static "EMPLOYEE" and "EMPLOYER" text (not wrapped in braces). They continue working as-is. New requests use `{VARIABLE}` syntax. During D.2, existing requests are updated to use `{EMPLOYEE}` and `{EMPLOYER}` variables where appropriate, which resolve to the same static terms by default.

---

## 5. Phase D.1 — Model Extension and Variable Resolver

**Goal**: Extend the domain model and build the substitution engine. Zero behavioral change. All existing tests pass.

**Estimated effort**: ~200 lines production code, ~50 new tests.

---

### Task D.1.1 — Extend DiscoveryRequest model

**File**: `src/employee_help/discovery/models.py`

Add two fields to `DiscoveryRequest`:

```python
@dataclass(frozen=True)
class DiscoveryRequest:
    id: str
    text: str  # May contain {VARIABLE} placeholders
    category: str
    is_selected: bool = True
    is_custom: bool = False
    order: int = 0
    notes: str | None = None
    # --- New fields ---
    applicable_roles: tuple[str, ...] = ("plaintiff", "defendant")
    applicable_claims: tuple[str, ...] = ()  # empty = all claims
```

`RFARequest` inherits the new fields automatically (it extends `DiscoveryRequest`).

**Acceptance criteria**:
- All existing tests pass without modification
- New fields accessible on all existing bank items via defaults
- Frozen dataclass behavior preserved

**Tests**: Unit tests for new field defaults, dataclass immutability, RFARequest inheritance.

---

### Task D.1.2 — Build variable resolver

**New file**: `src/employee_help/discovery/resolver.py` (~60 lines)

```python
def build_variable_map(case_info: CaseInfo) -> dict[str, str]:
    """Build the variable substitution map from case context."""

def resolve_text(template: str, variables: dict[str, str]) -> str:
    """Replace {PLACEHOLDER} variables in template text.
    Unknown variables pass through unchanged."""

def resolve_request(
    request: DiscoveryRequest,
    case_info: CaseInfo,
) -> DiscoveryRequest:
    """Return a new DiscoveryRequest with resolved text."""
```

Implementation: Use `str.format_map()` with a `defaultdict(lambda key: f"{{{key}}}")` so unknown keys are returned as-is.

**Acceptance criteria**:
- All 6 variables resolve correctly for both party roles
- Unknown variables pass through as `{UNKNOWN}`
- Empty CaseInfo fields produce sensible defaults (empty string, not crash)
- Entity names and individual names both work
- Pure function, no side effects, no imports outside discovery package

**Tests**: 15–20 unit tests covering all variable combinations, edge cases, and both party roles.

---

### Task D.1.3 — Build role and claim filter functions

**New file**: `src/employee_help/discovery/filters.py` (~40 lines)

```python
def filter_by_role(
    requests: list[DiscoveryRequest],
    party_role: PartyRole,
) -> list[DiscoveryRequest]:
    """Return only requests applicable to the given party role."""

def filter_by_claims(
    requests: list[DiscoveryRequest],
    claim_types: tuple[ClaimType, ...],
) -> list[DiscoveryRequest]:
    """Return requests applicable to any of the given claim types.
    Requests with empty applicable_claims pass through (universal)."""
```

**Acceptance criteria**:
- Requests with `applicable_roles=("plaintiff", "defendant")` pass both filters
- Requests with `applicable_roles=("plaintiff",)` are excluded for defendant role
- Requests with empty `applicable_claims` are never filtered out
- Requests with `applicable_claims=("feha_discrimination",)` are excluded when claim list doesn't include it

**Tests**: 10–12 unit tests covering combinations of role and claim filtering, empty inputs, universal requests.

---

### Task D.1.4 — Fix FUNCTIONALITY.md inflated numbers

**File**: `FUNCTIONALITY.md`

Replace all inflated bank item claims with actual current counts:
- "300+ customizable interrogatories" → "35 special interrogatories across 8 categories"
- "250+ document production requests" → "28 document requests across 14 categories"
- "200+ requests for admission" → "26 requests for admission across 6 categories (21 fact + 5 genuineness)"
- "750+ Request bank items" → "89 curated request bank items (SROGs + RFPDs + RFAs)"

Add note: "Request banks are being expanded to ~185 role-aware templates in Phase D.2."

**Acceptance criteria**: All numbers in FUNCTIONALITY.md match actual code.

---

### D.1 Gate

- [x] All existing tests pass (233 discovery tests verified, no breakage)
- [x] New unit tests pass (55 new tests: 16 model + 22 resolver + 17 filters)
- [x] `resolver.py` and `filters.py` have 100% branch coverage
- [x] FUNCTIONALITY.md numbers are accurate

---

## 6. Phase D.2 — Expand Request Banks

**Goal**: Add defendant-side requests, new categories, claim-gated variants, and variable-templated text. Banks grow from 89 to ~185.

**Estimated effort**: ~900 lines of request data, ~30 new bank integrity tests.

**Content source**: California Employment Law Discovery Playbook (PDF in `learning/market research/discovery/requests/`).

---

### Task D.2.1 — Annotate existing requests

**Files**: `srogs.py`, `rfpds.py`, `rfas.py`

Update all 89 existing requests with:

1. `applicable_roles=("plaintiff",)` — they are all plaintiff-side
2. Appropriate `applicable_claims` for claim-specific requests:
   - `srog_wage_*` → `applicable_claims=("wage_theft", "meal_rest_break", "overtime", "misclassification")`
   - `rfa_wage_*` → same
   - All others → `applicable_claims=()` (universal, no gate)
3. Replace static "EMPLOYEE" and "EMPLOYER" in text with `{EMPLOYEE}` and `{EMPLOYER}` variables where the term refers to the specific party (not the legal definition)

**Acceptance criteria**:
- All existing tests pass (resolved text matches original static text for plaintiff propounding, since `{EMPLOYEE}` resolves to the plaintiff name which was previously "EMPLOYEE")
- Every request has explicit `applicable_roles` annotation
- Bank getter functions still work identically

**Tests**: Verify bank counts unchanged, category membership unchanged, annotation completeness (no request missing `applicable_roles`).

---

### Task D.2.2 — Add new SROG categories and requests

**File**: `src/employee_help/discovery/srogs.py`

**New categories** added to `SROG_CATEGORIES`:

| Category Key | Label | Side | Claim Gate |
|-------------|-------|------|------------|
| `contention_interrogatories` | Contention Interrogatories (Affirmative Defenses) | plaintiff | none |
| `accommodation` | Accommodation and Interactive Process | plaintiff | `feha_failure_to_accommodate`, `feha_failure_interactive_process` |
| `communications` | Communications | plaintiff | none |
| `factual_basis` | Factual Basis for Claims | defendant | none |
| `emotional_distress` | Emotional Distress and Medical Treatment | defendant | none |
| `mitigation` | Mitigation of Damages | defendant | none |
| `prior_employment` | Prior Employment and Claims History | defendant | none |
| `social_media_recordings` | Social Media, Communications, and Recordings | defendant | none |

**New requests** (~30 total):

*Plaintiff-only contention interrogatories (3):*
- State all facts supporting contention that adverse action was for stated legitimate reason
- State all facts supporting affirmative defense of [after-acquired evidence / failure to mitigate / statute of limitations]
- State all facts supporting contention that employer took all reasonable steps to prevent discrimination/harassment/retaliation

*Plaintiff-only accommodation/interactive process (2, FEHA-gated):*
- Describe every step taken to engage in interactive process after learning of accommodation need
- Identify every accommodation considered and reason each was not provided

*Plaintiff-only communications (3):*
- Identify communications between decision-maker and others concerning employee's performance/complaint/accommodation
- Identify communications between employer personnel and outside persons concerning employee's termination/claims
- Identify any person who expressed disagreement with adverse action decision

*Defendant-only factual basis (4):*
- State all facts supporting contention that adverse action was motivated by protected characteristic/activity
- For each instance of discrimination/harassment/retaliation alleged, state date, location, persons involved, what was said/done
- Identify each person who made statements reflecting discriminatory animus, state each statement, date, witnesses
- State all facts supporting contention that employer's stated reason was pretextual

*Defendant-only witnesses (2):*
- Identify each person with knowledge of facts relevant to claims and describe subject matter
- Identify each person plaintiff told about alleged discrimination/harassment/retaliation, state date and substance

*Defendant-only emotional distress/medical (4):*
- Describe each symptom of emotional distress contended to be caused by adverse action
- Identify each health care provider for emotional/mental health treatment during 5 years preceding through present
- Identify each prescription medication for emotional/mental health condition during relevant period
- State whether diagnosed/treated for emotional/mental condition prior to employment with employer

*Defendant-only mitigation (3):*
- Identify every employer applied to after adverse action, state date, position, outcome
- Identify every source of income from adverse action date through present
- State whether declined/failed to pursue any employment opportunity, describe each and reason

*Defendant-only prior employment/claims (2):*
- Identify every employer during 10 years preceding employment, state title, dates, reason for leaving
- State whether ever filed lawsuit, administrative charge, workers' comp claim against any employer

*Defendant-only social media/recordings (2):*
- Identify all social media accounts during relevant period
- State whether made any recording of events alleged in complaint, describe each

*Shared with variables (3):*
- Employment commencement/titles/dates (adapt subject by `{RESPONDING_PARTY}`)
- Supervisor identification during employment
- Compensation at each stage

**Target SROG count**: ~65 templates.

---

### Task D.2.3 — Add new RFPD categories and requests

**File**: `src/employee_help/discovery/rfpds.py`

**New categories** added to `RFPD_CATEGORIES`:

| Category Key | Label | Side | Claim Gate |
|-------------|-------|------|------------|
| `esi` | Electronically Stored Information | plaintiff | none |
| `litigation_hold` | Litigation Hold and Preservation | plaintiff | none |
| `accommodation_docs` | Reasonable Accommodation Documents | plaintiff | `feha_failure_to_accommodate`, `feha_failure_interactive_process` |
| `medical_records` | Medical and Therapy Records | defendant | none |
| `financial_records` | Financial Records and Tax Returns | defendant | none |
| `job_search_docs` | Job Search and Mitigation Documents | defendant | none |
| `prior_employment_docs` | Prior Employment Records | defendant | none |
| `personal_records` | Diaries, Journals, and Personal Notes | defendant | none |
| `social_media_docs` | Social Media and Recordings | defendant | none |
| `govt_agency_docs` | Government Agency Communications | defendant | none |

**New requests** (~30 total):

*Plaintiff-only (8):*
- ESI: All electronically stored information in native format with metadata intact
- Litigation hold: All litigation hold notices and preservation communications
- Accommodation: Communications regarding accommodation request and interactive process (FEHA-gated)
- Accommodation: Evaluation of ability to perform essential functions (FEHA-gated)
- Accommodation: Accommodations provided to other employees at same facility (FEHA-gated)
- Decision-maker/alleged harasser complete personnel file including evaluations and disciplinary records
- Prior complaints about alleged harasser/decision-maker during 10 years preceding
- Documents reviewed/considered/relied upon in making adverse action decision

*Defendant-only (20):*
- Communications about claims (3): All communications about adverse action, govt agency correspondence, CRD/EEOC documents
- Medical/therapy (3): Post-incident treatment records, 5-year pre-employment mental health history, medication/prescription records
- Financial (4): Federal/state tax returns, income since adverse action (pay stubs/W-2s/1099s), severance/separation docs, unemployment/disability benefits docs
- Job search (3): Applications/resumes/cover letters/recruiter communications, offers received (accepted or declined), self-employment/freelance/consulting records
- Prior employment (2): Employment records during 10 years preceding, prior lawsuits/charges/grievances docs
- Personal (1): Diaries, journals, logs, calendars about employment or claims
- Social media (1): Screenshots/posts about employment, adverse action, emotional state
- Recordings (1): Audio/video/photos made during employment
- Supporting documents (2): All documents relied upon to support complaint allegations, all documents received from employer during employment

**Target RFPD count**: ~58 templates.

---

### Task D.2.4 — Add new RFA categories and requests

**File**: `src/employee_help/discovery/rfas.py`

**New categories** added to `RFA_CATEGORIES`:

| Category Key | Label | Side | Claim Gate |
|-------------|-------|------|------------|
| `discrimination_facts` | Discrimination, Harassment, and Retaliation | plaintiff | none |
| `comparator_facts` | Comparator and Similar Treatment | plaintiff | none |
| `damages_facts` | Damages and Benefits | plaintiff | none |
| `accommodation_facts` | Disability Accommodation | plaintiff | `feha_failure_to_accommodate`, `feha_failure_interactive_process` |
| `performance_facts` | Performance and Disciplinary History | defendant | none |
| `policies_compliance` | Policies and Complaint Procedures | defendant | none |
| `legitimate_reasons` | Legitimate Business Reasons | defendant | none |
| `damages_limitations` | Damages Limitations | defendant | none |
| `mitigation_facts` | Mitigation of Damages | defendant | none |
| `prior_claims` | Prior Employment and Claims | defendant | none |
| `direct_evidence` | Lack of Direct Evidence | defendant | none |

**New requests** (~36 total):

*Plaintiff-only (12):*
- Discrimination/harassment/retaliation (5): Protected characteristic as motivating reason, temporal proximity of adverse action to protected activity, harasser's specific statements/conduct, other employees complained about harasser, no alternative position offered
- Comparators (3): Comparator held same position, comparator engaged in same conduct and was not disciplined, comparator not member of same protected class
- Damages (2): Annual base salary at time of adverse action, eligibility for health/retirement/bonus benefits
- Accommodation (3, FEHA-gated): Requested reasonable accommodation on specific date, no timely good-faith interactive process, accommodation would not impose undue hardship

*Defendant-only (22):*
- Performance/discipline (5): Received written warning on date, verbally counseled about specific issue, evaluation noted deficiencies, aware of performance standard as requirement, failed to meet specific metric
- Policies/compliance (6): Received employee handbook, signed acknowledgment, handbook contained anti-discrimination policy, handbook described complaint procedure, did not use internal complaint procedure, attended anti-harassment training
- Legitimate business reasons (3): Decision-maker stated legitimate reason, supervisor met to discuss performance, engaged in specific cited conduct on date
- Damages limitations (4): Did not seek medical doctor treatment, did not seek mental health professional treatment, experienced anxiety/depression prior to employment, received unemployment/severance benefits
- Mitigation (3): Did not apply for employment during period following adverse action, offered position and declined, earned specific income during 12 months following
- Prior claims (3): Filed complaint against prior employer, terminated from prior employer, did not disclose specific fact on application
- Direct evidence (2): No person made statement referencing protected characteristic as reason, no person made derogatory comment about protected characteristic

*Shared genuineness (2):*
- Document attached as exhibit is genuine (variable subject)
- Document was maintained in ordinary course of business

**Target RFA count**: ~62 templates.

---

### Task D.2.5 — Bank integrity tests

**New test file**: `tests/test_discovery_bank_integrity.py`

Verify across all three banks:
- No duplicate request IDs
- Every request references a valid category
- Every category has at least one request
- Every request has a non-empty `applicable_roles` tuple
- `applicable_claims` values (when non-empty) reference valid `ClaimType` values
- Template variables in text are from the known variable registry
- Plaintiff-only requests don't reference defendant-only categories
- Request count per bank matches expected totals

**Tests**: ~30 integrity tests.

---

### D.2 Gate

- [x] All existing tests pass (2438 total, 0 failures)
- [x] Bank integrity tests pass (51 new tests)
- [x] SROG bank has 58 templates across 16 categories
- [x] RFPD bank has 52 templates across 24 categories
- [x] RFA bank has 67 templates across 17 categories
- [x] Total bank size is 177 templates
- [x] All templates have correct `applicable_roles` and `applicable_claims` annotations
- [x] Content reviewed against CCP requirements

---

## 7. Phase D.3 — API and Claim Mapping Integration

**Goal**: Wire role-aware filtering and variable resolution into the API layer. Frontend receives role-appropriate banks with resolved text.

**Estimated effort**: ~150 lines production changes, ~40 new tests.

---

### Task D.3.1 — Update claim_mapping.py for role-awareness

**File**: `src/employee_help/discovery/claim_mapping.py`

Extend `DiscoverySuggestions` to support role-specific category overrides:

```python
@dataclass(frozen=True)
class DiscoverySuggestions:
    # Existing fields (unchanged)
    disc001_sections: tuple[str, ...]
    disc002_sections: tuple[str, ...]
    srog_categories: tuple[str, ...]
    rfpd_categories: tuple[str, ...]
    rfa_categories: tuple[str, ...]
    # New: role-specific overrides (None = use base categories)
    srog_categories_defendant: tuple[str, ...] | None = None
    rfpd_categories_defendant: tuple[str, ...] | None = None
    rfa_categories_defendant: tuple[str, ...] | None = None
```

Add helper:
```python
def categories_for_role(
    self, tool: str, role: PartyRole,
) -> tuple[str, ...]:
    """Return role-specific categories, falling back to base."""
```

Rename existing base category tuples to serve as the plaintiff default. Add defendant-specific category tuples for each of the 19 claim types in `CLAIM_DISCOVERY_MAP`.

Update `merge_suggestions()` to merge role-specific fields.

**Acceptance criteria**:
- Existing behavior preserved when no role-specific override exists
- Defendant role returns defendant-appropriate categories
- Merged suggestions correctly union role-specific fields

**Tests**: Extend existing claim mapping tests with role-parameterized variants.

---

### Task D.3.2 — Update bank API endpoint with role filtering

**File**: `src/employee_help/api/discovery_routes.py`

Add optional `party_role` query parameter to `GET /api/discovery/banks/{tool}`:

```python
@discovery_router.get("/banks/{tool}")
async def get_discovery_bank(
    tool: str,
    party_role: str | None = None,
    # Future: case_info context for variable resolution
):
```

When `party_role` is provided:
1. Import and call `filter_by_role()` on the bank
2. Filter categories to only those with at least one remaining request
3. Return the filtered bank

When `party_role` is omitted: return full bank (backwards compatible).

**Acceptance criteria**:
- Without `party_role`: response identical to current behavior
- With `party_role=plaintiff`: returns only plaintiff + shared requests
- With `party_role=defendant`: returns only defendant + shared requests
- Categories with zero filtered requests are omitted

**Tests**: API tests for both roles and for omitted role.

---

### Task D.3.3 — Update suggest endpoint with role-aware mapping

**File**: `src/employee_help/api/discovery_routes.py`

In the `srogs`, `rfpds`, `rfas` branches of `POST /api/discovery/suggest`:

```python
merged = get_suggestions_for_claims(claim_types)
categories = merged.categories_for_role("srogs", party_role)
items = get_srogs_for_categories(categories)
items = filter_by_role(items, party_role)
items = filter_by_claims(items, tuple(claim_types))
```

**Acceptance criteria**:
- Plaintiff + FEHA discrimination → suggests plaintiff SROG categories + comparator + contention
- Defendant + FEHA discrimination → suggests defendant SROG categories (factual basis, emotional distress, mitigation, etc.)
- Suggested item count reflects filtered bank

**Tests**: Parameterized tests for suggest endpoint with both roles.

---

### Task D.3.4 — Add variable resolution to API responses

**File**: `src/employee_help/api/discovery_routes.py`

When the bank endpoint receives `party_role` (and optionally case context via new query params or a future POST variant), resolve template variables in the returned item text.

For MVP: If `party_role` is provided but no case names are available, use the definition-style defaults ("EMPLOYEE", "EMPLOYER", "Plaintiff", "Defendant"). When case context is available (from frontend discovery context), resolve to actual party names.

**Implementation**: Import `resolve_text` and `build_variable_map` from `resolver.py`. Apply to each item's text before returning.

**Acceptance criteria**:
- Template variables in returned text are resolved when context is available
- Without context, raw templates are returned (frontend handles display)
- Resolved text reads naturally in both plaintiff and defendant contexts

---

### Task D.3.5 — Update API schemas

**File**: `src/employee_help/api/schemas.py`

- Add `applicable_roles` and `applicable_claims` fields to `DiscoveryBankItemInfo`
- Add optional `party_role` query param documentation

**Tests**: Schema validation tests.

---

### D.3 Gate

- [x] All existing tests pass (2510 total, 0 failures)
- [x] Bank endpoint returns role-filtered results when `party_role` is provided
- [x] Bank endpoint returns full bank when `party_role` is omitted (backwards compatible)
- [x] Suggest endpoint uses role-aware category mapping
- [x] Variable resolution works for both roles
- [x] 49 new API tests pass

---

## 8. Phase D.4 — Frontend Integration

**Goal**: The UI shows role-appropriate requests with resolved variables. Category pills and request lists adapt to the selected party role.

**Estimated effort**: ~200 lines frontend changes, ~10 new E2E tests.

---

### Task D.4.1 — Update discovery-api.ts types and client

**File**: `frontend/lib/discovery-api.ts`

- `getBankRequests(tool, partyRole?)` — pass `party_role` as query parameter when available
- `DiscoveryRequest` type gains optional `applicable_roles` and `applicable_claims` fields
- Add `resolveVariables(text: string, caseInfo: CaseInfo): string` utility (~15 lines) for client-side preview resolution when bank returns raw templates

**Acceptance criteria**:
- Bank fetch includes party_role from discovery context
- TypeScript types match updated API schema

---

### Task D.4.2 — Update request-builder.tsx for resolved text

**File**: `frontend/components/discovery/request-builder.tsx`

- Display resolved text in request rows (call `resolveVariables` on each `request.text`)
- Show a subtle placeholder indicator for any unresolved `{VARIABLE}` remaining (styled differently, e.g., highlighted background)
- Category pills only show categories that have requests after role filtering

**Acceptance criteria**:
- Plaintiff user sees plaintiff + shared requests only
- Defendant user sees defendant + shared requests only
- Category counts reflect filtered requests
- Resolved text reads naturally

---

### Task D.4.3 — Update wizard pages to pass party_role in bank fetch

**Files**:
- `frontend/app/tools/discovery/special-interrogatories/page.tsx`
- `frontend/app/tools/discovery/request-production/page.tsx`
- `frontend/app/tools/discovery/request-admission/page.tsx`

When fetching the bank via `getBankRequests()`, pass `partyRole` from the discovery context (set during the case info step).

**Acceptance criteria**:
- Changing party role in case info step causes bank to re-fetch with new role
- Bank items update immediately after role change

---

### Task D.4.4 — Update preview-panel.tsx for resolved text

**File**: `frontend/components/discovery/preview-panel.tsx`

- Show fully resolved text in the document preview
- Highlight any remaining unresolved variables as warnings (visual cue that case info is incomplete)

---

### Task D.4.5 — Add E2E tests for defendant-side flows

**Files**: New or updated Playwright spec files

Add at minimum:
- 1 test: Defendant SROGs — verify defendant categories appear, plaintiff categories hidden
- 1 test: Defendant RFPDs — verify defendant categories appear, document generates
- 1 test: Defendant RFAs — verify defendant categories appear, fact/genuineness tracking works
- 1 test: Role switch — change party role mid-wizard, verify bank re-filters
- 1 test: Variable resolution — verify resolved text in preview matches case info

**Acceptance criteria**:
- All existing 49 E2E tests pass
- 5+ new E2E tests pass for defendant-side and role-switching flows

---

### D.4 Gate

- [x] All existing 49 E2E tests pass (no regressions, TypeScript + ESLint clean)
- [x] 6 new E2E tests (discovery-defendant.spec.ts)
- [x] Defendant-side wizard works end-to-end (case info → select → preview → generate)
- [x] Variable resolution visible in preview (ResolvedText component with actual party names)
- [x] Category filtering works for both roles (bank re-fetches with party_role on role change)
- [x] No regressions in plaintiff-side flows (388 backend discovery tests pass)

---

## 9. Phase D.5 — Documentation and Validation

**Goal**: Correct all documentation, validate end-to-end with realistic cases, update seed files.

**Estimated effort**: ~100 lines documentation changes.

---

### Task D.5.1 — Update FUNCTIONALITY.md with final counts

**File**: `FUNCTIONALITY.md`

Rewrite Section 4 (Discovery Document Generation) request bank subsection with actual post-implementation counts:

```
- **SROGs**: ~65 role-aware templates across 16 categories (plaintiff, defendant, shared)
- **RFPDs**: ~58 role-aware templates across 24 categories
- **RFAs**: ~62 role-aware templates across 17 categories (with fact/genuineness tracking)
- **Total**: ~185 curated request templates with role filtering and variable substitution
```

---

### Task D.5.2 — Update seed files

**Files**: `seed-files/discovery/*.md`

- Update `case-defendant-side.md` to reference defendant-specific categories and request IDs
- Verify all 5 seed files have correct recommended categories for their party role
- Add notes about variable resolution in seed file headers

---

### Task D.5.3 — End-to-end validation

Generate and review complete discovery sets for these four scenarios:

| Scenario | Party Role | Claims | Expected Bank |
|----------|-----------|--------|---------------|
| FEHA discrimination | Plaintiff | `feha_discrimination`, `feha_retaliation` | Plaintiff categories + comparator + contention |
| FEHA discrimination defense | Defendant | `feha_discrimination` | Defendant categories (factual basis, emotional distress, mitigation, prior employment) |
| Wage & hour | Plaintiff | `wage_theft`, `meal_rest_break`, `overtime` | Plaintiff categories + wage-specific + claim-gated |
| Disability accommodation | Plaintiff | `feha_failure_to_accommodate`, `feha_failure_interactive_process` | Plaintiff categories + accommodation (FEHA-gated) |

For each: verify correct requests appear, variables resolve, DOCX generates cleanly, and excluded requests don't leak through.

---

### Task D.5.4 — Update MEMORY.md

Record:
- Phase D completion status
- New bank counts and category counts
- Architectural decisions made
- New files created

---

### D.5 Gate

- [x] FUNCTIONALITY.md numbers match actual implementation (58/52/67, test table updated with 3 new backend + 1 E2E test rows, 55 E2E total)
- [x] All 5 seed files updated (variable resolution notes, correct category names and counts)
- [x] 4 validation scenarios pass (all 5 invariants verified: role isolation, claim-gating, variable resolution)
- [x] MEMORY.md updated
- [x] All tests pass (2,596+ backend, 55 E2E)

---

## 10. Request Bank Inventory

### SROGs (~65 total across 16 categories)

| Category | Side | Requests | Claim Gate |
|----------|------|----------|------------|
| Employment Relationship | shared | 4 | none |
| Adverse Employment Actions | plaintiff | 6 | none |
| Comparator / Similarly Situated | plaintiff | 4 | none |
| Decision Makers | plaintiff | 3 | none |
| Investigation and Complaints | plaintiff | 5 | none |
| Policies and Procedures | plaintiff | 4 | none |
| Damages | plaintiff | 4 | none |
| Wages and Hours | plaintiff | 5 | wage claims |
| Contention Interrogatories | plaintiff | 3 | none |
| Accommodation and Interactive Process | plaintiff | 2 | FEHA accommodation |
| Communications | plaintiff | 3 | none |
| Factual Basis for Claims | defendant | 4 | none |
| Emotional Distress and Medical | defendant | 4 | none |
| Mitigation of Damages | defendant | 3 | none |
| Prior Employment and Claims | defendant | 2 | none |
| Social Media, Communications, Recordings | defendant | 2 | none |

### RFPDs (~58 total across 24 categories)

| Category | Side | Requests | Claim Gate |
|----------|------|----------|------------|
| Personnel Records | plaintiff | 3 | none |
| Performance Evaluations | plaintiff | 2 | none |
| Discipline and Corrective Actions | plaintiff | 2 | none |
| Termination / Adverse Action | plaintiff | 3 | none |
| Policies and Handbooks | plaintiff | 3 | none |
| Investigation Documents | plaintiff | 3 | none |
| Communications | plaintiff | 2 | none |
| Comparator Documents | plaintiff | 2 | none |
| Compensation and Payroll | plaintiff | 3 | none |
| Time Records | plaintiff | 1 | wage claims |
| Training Records | plaintiff | 1 | none |
| Job Descriptions | plaintiff | 1 | none |
| Organizational Charts | plaintiff | 1 | none |
| Insurance | plaintiff | 1 | none |
| ESI | plaintiff | 2 | none |
| Litigation Hold and Preservation | plaintiff | 1 | none |
| Accommodation Documents | plaintiff | 3 | FEHA accommodation |
| Medical and Therapy Records | defendant | 3 | none |
| Financial Records and Tax Returns | defendant | 4 | none |
| Job Search and Mitigation | defendant | 3 | none |
| Prior Employment Records | defendant | 2 | none |
| Diaries, Journals, Personal Notes | defendant | 1 | none |
| Social Media and Recordings | defendant | 2 | none |
| Government Agency Communications | defendant | 3 | none |

### RFAs (~62 total across 17 categories)

| Category | Side | Requests | Claim Gate |
|----------|------|----------|------------|
| Employment Relationship Facts | shared | 4 | none |
| Adverse Employment Action Facts | plaintiff | 5 | none |
| Policies and Procedures | plaintiff | 4 | none |
| Complaints and Investigation | plaintiff | 4 | none |
| Wages and Hours | plaintiff | 4 | wage claims |
| Genuineness of Documents | shared | 7 | none |
| Discrimination, Harassment, Retaliation | plaintiff | 5 | none |
| Comparator and Similar Treatment | plaintiff | 3 | none |
| Damages and Benefits | plaintiff | 2 | none |
| Disability Accommodation | plaintiff | 3 | FEHA accommodation |
| Performance and Disciplinary History | defendant | 5 | none |
| Policies and Complaint Procedures | defendant | 6 | none |
| Legitimate Business Reasons | defendant | 3 | none |
| Damages Limitations | defendant | 4 | none |
| Mitigation of Damages | defendant | 3 | none |
| Prior Employment and Claims | defendant | 3 | none |
| Lack of Direct Evidence | defendant | 2 | none |

---

## 11. Summary

| Phase | Tasks | Files Changed | New Tests | LOC (approx) | Depends On |
|-------|-------|---------------|-----------|--------------|------------|
| **D.1** Model + Resolver | 4 | 4 (2 new, 2 modified) | ~50 | ~200 | — |
| **D.2** Bank Expansion | 5 | 4 (1 new, 3 modified) | ~30 | ~900 | D.1 |
| **D.3** API Integration | 5 | 3 modified | ~40 | ~150 | D.1, D.2 |
| **D.4** Frontend | 5 | 6 modified | ~10 E2E | ~200 | D.3 |
| **D.5** Docs + Validation | 4 | 5 modified | — | ~100 | D.4 |
| **Total** | **23 tasks** | **~15 files** | **~130 tests** | **~1,550** | Sequential |

### Key Principles

- **No new dependencies**: Pure Python data, no YAML loaders, no template engines beyond `str.format_map`
- **Backwards compatible**: Every new field has a default. Existing tests pass through D.1 without modification
- **Non-duplicative**: Shared requests use variable substitution, not separate plaintiff/defendant copies
- **Claim-gated**: Specialty requests (accommodation, wage) only surface when relevant claims are selected
- **Role-filtered**: Banks show only relevant requests for the user's party role. No scrolling past irrelevant content
- **Content-reviewed**: Every request must be CCP-compliant and reflect prevailing California employment litigation practice
