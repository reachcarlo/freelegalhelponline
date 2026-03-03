# Discovery Tools — Feature Specification & Implementation Plan

> **Status**: Planning
> **Date**: 2026-03-02
> **Scope**: Four California employment law discovery tools (FROGs, SROGs, RFPDs, RFAs)
> **Target users**: Attorneys (attorney mode only — not consumer mode)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Competitive Landscape](#2-competitive-landscape)
3. [Legal Framework](#3-legal-framework)
4. [Architecture Overview](#4-architecture-overview)
5. [Shared Components](#5-shared-components)
6. [Tool 1: Form Interrogatories General (FROGs — DISC-001)](#6-tool-1-form-interrogatories-general-frogs--disc-001)
7. [Tool 2: Form Interrogatories Employment (FROGs — DISC-002)](#7-tool-2-form-interrogatories-employment-frogs--disc-002)
8. [Tool 3: Special Interrogatories (SROGs)](#8-tool-3-special-interrogatories-srogs)
9. [Tool 4: Requests for Production of Documents (RFPDs)](#9-tool-4-requests-for-production-of-documents-rfpds)
10. [Tool 5: Requests for Admission (RFAs)](#10-tool-5-requests-for-admission-rfas)
11. [Data Schema](#11-data-schema)
12. [Document Generation Engine](#12-document-generation-engine)
13. [UI/UX Design](#13-uiux-design)
14. [Phased Implementation Plan](#14-phased-implementation-plan)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. Executive Summary

### What We're Building

A guided workflow system that produces **ready-to-file** California employment law discovery documents:

| Tool | Output Format | Judicial Council Form | Template Type |
|------|--------------|----------------------|---------------|
| Form Interrogatories — General | Editable PDF | DISC-001 | Fill existing JC PDF |
| Form Interrogatories — Employment | Editable PDF | DISC-002 | Fill existing JC PDF |
| Special Interrogatories | Editable Word (.docx) | None (pleading paper) | Jinja2 DOCX template |
| Requests for Production | Editable Word (.docx) | None (pleading paper) | Jinja2 DOCX template |
| Requests for Admission | Editable Word (.docx) | DISC-020 cover + pleading paper | Hybrid: PDF cover + DOCX attachment |

### Key Design Principles

1. **Plaintiff/defendant agnostic**: Same base questions reused regardless of side. Party role affects which form interrogatories are auto-suggested, not the workflow structure.
2. **Comprehensive by default**: Better to generate a full set that an attorney can trim than a sparse set requiring manual additions.
3. **Employment-law focused**: Every guided question, every suggested interrogatory/request, and every template is calibrated for California employment litigation.
4. **Shared case information**: Collect once, reuse across all four tools. Case info stored client-side for MVP; backend schema ready for persistence.
5. **Editable output**: Attorneys must be able to modify the output. PDFs remain fillable (not flattened). DOCX files are fully editable Word documents.

### Market Gap

No existing product provides a guided, employment-law-specific discovery generator for California. The closest competitors:
- **Briefpoint** ($89/mo) — response-only, not propounding
- **Legion.law** — California-specific but attorney-only AI, no guided wizard
- **AI.Law** ($389/mo) — multi-jurisdiction AI, no employment-specific templates
- **Docassemble** — open-source platform but zero California discovery interviews exist
- **PDF fill tools** (DocHub, pdfFiller) — manual fill, zero guidance

We are the first product to connect **employment rights knowledge** (our RAG knowledge base) to **discovery document generation** through a guided workflow.

---

## 2. Competitive Landscape

### Direct Competitors

| Product | Propounding | Responding | CA Employment | Guided Wizard | Pro Se | Pricing |
|---------|:---------:|:----------:|:------------:|:-------------:|:------:|---------|
| Briefpoint | No | Yes | No | No | No | $89/mo |
| Legion.law | Yes | Yes | No | No | No | Undisclosed |
| AI.Law | Yes | Yes | No | No | No | $389/mo |
| Eve.Legal | Yes | Yes | No | No | No | Undisclosed |
| StrongSuit | No | Yes | Partial | No | No | $249/mo |
| Docassemble | Possible | Possible | No templates | Yes (generic) | Yes | Free |
| **Employee Help** | **Yes** | **Future** | **Yes** | **Yes** | **Yes** | **TBD** |

### Our Differentiators

1. **Employment-law-specific guided workflow** — auto-suggests interrogatories/requests based on claim type
2. **RAG-backed intelligence** — connects to our 24K-chunk knowledge base for statutory citations
3. **Both consumer and attorney output** — guided wizard accessible to pro se; output format meets attorney standards
4. **California-native** — CCP compliance built in (35-SROG limit tracking, service deadline calculations, proper formatting)
5. **Dual output** — fillable PDF for JC forms + editable DOCX on pleading paper

---

## 3. Legal Framework

### CCP Discovery Rules Summary

| Rule | SROGs | FROGs | RFPDs | RFAs |
|------|-------|-------|-------|------|
| **Governing CCP** | 2030.010-2030.410 | 2030.010-2030.410 | 2031.010-2031.510 | 2033.010-2033.420 |
| **Numeric limit** | 35 (without declaration) | Unlimited | Unlimited | 35 (without declaration; genuineness unlimited) |
| **Subparts allowed** | No | Yes (pre-approved) | N/A | No |
| **Compound questions** | No | Yes (pre-approved) | N/A | No |
| **Response deadline** | 30 days (+5 mail, +2 e-service) | Same | Same | Same |
| **Verification** | Under oath | Under oath | Written statement | Under oath |
| **Continuing duty** | No | No | No | N/A |
| **Format** | Pleading paper | JC Form (DISC-001/002) | Pleading paper | DISC-020 cover + pleading paper |

### Timing Rules (CCP 2030.020)

- **Plaintiff**: May serve 10 days after service of summons on responding party, or after appearance
- **Defendant**: May serve at any time
- **Discovery cutoff**: 30 days before trial date (CCP 2024.020)
- **Motion cutoff**: 15 days before trial date

### Service Method Extensions (CCP 1013 / 1010.6)

| Method | Additional Days |
|--------|----------------|
| Personal service | +0 |
| Mail (in-state) | +5 calendar days |
| Mail (out-of-state) | +10 calendar days |
| Electronic service | +2 court days |
| Overnight delivery | +2 court days |

### Declaration of Necessity (CCP 2030.050 / 2033.050)

Required when exceeding 35 SROGs or 35 RFAs. Must contain:
1. Declarant identity
2. Identification of responding party
3. Acknowledgment that total exceeds 35
4. Count of previously propounded requests
5. Personal examination certification
6. Justification (complexity, burden, expedience)
7. No improper purpose certification
8. Executed under penalty of perjury

### Standard Employment Discovery Definitions

These defined terms (ALL CAPITALS per CCP 2030.060(e)) are shared across SROGs, RFPDs, and RFAs:

| Term | Definition |
|------|-----------|
| **DOCUMENT** | A writing as defined in Evidence Code section 250, including originals or copies of handwriting, typewriting, printing, photographs, ESI, and every other means of recording upon any tangible thing |
| **COMMUNICATION** | The transmittal of information in the form of facts, ideas, inquiries, or otherwise, between two or more PERSONS |
| **PERSON** | A natural person, firm, association, organization, partnership, business, trust, LLC, corporation, or public entity |
| **YOU/YOUR** | The responding party, its agents, employees, representatives, attorneys, and anyone acting on its behalf |
| **RELATING TO / CONCERNING** | Referring to, describing, evidencing, constituting, mentioning, or being in any way logically or factually connected with the matter described |
| **IDENTIFY (person)** | State full name, last known address, telephone number, and relationship to the parties |
| **IDENTIFY (document)** | State type, date, author, recipients, subject matter, and present location/custodian |
| **EMPLOYEE** | [Plaintiff/Defendant name] — the person who provides services in an EMPLOYMENT relationship |
| **EMPLOYER** | [Plaintiff/Defendant name] — the entity that employs the EMPLOYEE |
| **EMPLOYMENT** | A relationship in which EMPLOYEE provides services requested by or on behalf of EMPLOYER, other than an independent contractor relationship |
| **ADVERSE EMPLOYMENT ACTION** | Any TERMINATION, suspension, demotion, reprimand, loss of pay, failure/refusal to hire, failure/refusal to promote, or other action adversely affecting EMPLOYEE's rights or interests |
| **TERMINATION** | Actual or constructive termination including discharge, firing, layoff, resignation, or completion of employment term |

---

## 4. Architecture Overview

### System Diagram

```
                           ┌─────────────────────────────┐
                           │     Frontend (Next.js)       │
                           │                              │
                           │  ┌───────────────────────┐   │
                           │  │  Discovery Wizard UI   │   │
                           │  │  (multi-step workflow) │   │
                           │  └──────────┬────────────┘   │
                           │             │                 │
                           │  ┌──────────▼────────────┐   │
                           │  │  Client-side State     │   │
                           │  │  (case info + choices) │   │
                           │  └──────────┬────────────┘   │
                           └─────────────┼────────────────┘
                                         │ POST /api/discovery/generate
                                         ▼
                           ┌─────────────────────────────┐
                           │     FastAPI Backend          │
                           │                              │
                           │  ┌───────────────────────┐   │
                           │  │  Discovery Router      │   │
                           │  │  (validation, routing) │   │
                           │  └──────────┬────────────┘   │
                           │             │                 │
                           │  ┌──────────▼────────────┐   │
                           │  │  Discovery Engine      │   │
                           │  │  (tool modules)        │   │
                           │  └──────────┬────────────┘   │
                           │             │                 │
                           │  ┌──────────▼────────────┐   │
                           │  │  Document Generator    │   │
                           │  │  pypdf (PDF filling)   │   │
                           │  │  docxtpl (DOCX gen)    │   │
                           │  └──────────┬────────────┘   │
                           │             │                 │
                           │  ┌──────────▼────────────┐   │
                           │  │  File Response         │   │
                           │  │  (StreamingResponse)   │   │
                           │  └───────────────────────┘   │
                           └─────────────────────────────┘
```

### Module Layout

```
src/employee_help/
├── discovery/                          # NEW: Discovery tool modules
│   ├── __init__.py
│   ├── models.py                       # Shared dataclasses & enums
│   ├── case_info.py                    # Case information schema
│   ├── definitions.py                  # Standard legal definitions
│   ├── frogs_general.py               # DISC-001 form interrogatories
│   ├── frogs_employment.py            # DISC-002 form interrogatories
│   ├── srogs.py                       # Special interrogatories engine
│   ├── rfpds.py                       # Request for production engine
│   ├── rfas.py                        # Request for admission engine
│   └── generator/                      # Document generation
│       ├── __init__.py
│       ├── pdf_filler.py              # pypdf-based PDF form filling
│       ├── docx_builder.py            # docxtpl-based DOCX generation
│       └── templates/                  # Template files
│           ├── disc001.pdf            # Official JC form (downloaded)
│           ├── disc002.pdf            # Official JC form (downloaded)
│           ├── disc020.pdf            # Official JC form (RFA cover)
│           ├── srog_template.docx     # Pleading paper template
│           ├── rfpd_template.docx     # Pleading paper template
│           └── rfa_template.docx      # Pleading paper template

frontend/
├── app/tools/discovery/
│   ├── page.tsx                       # Discovery tools landing page
│   ├── frogs-general/page.tsx         # DISC-001 workflow page
│   ├── frogs-employment/page.tsx      # DISC-002 workflow page
│   ├── special-interrogatories/page.tsx
│   ├── request-production/page.tsx
│   └── request-admission/page.tsx
├── components/discovery/
│   ├── case-info-form.tsx             # Shared case info collection
│   ├── claim-selector.tsx             # Employment claim type selector
│   ├── party-role-selector.tsx        # Plaintiff/defendant toggle
│   ├── interrogatory-picker.tsx       # Checkbox tree for FROGs
│   ├── request-builder.tsx            # Add/edit/remove requests (SROGs/RFPDs/RFAs)
│   ├── definition-editor.tsx          # Edit standard definitions
│   ├── wizard-stepper.tsx             # Progress bar / step indicator
│   ├── wizard-navigation.tsx          # Back/Next/Generate buttons
│   ├── preview-panel.tsx              # Live document preview
│   └── download-button.tsx            # Download generated document
└── lib/
    └── discovery-api.ts               # API client for discovery endpoints
```

### Dependencies (new)

```toml
# pyproject.toml [project.optional-dependencies]
discovery = [
    "pypdf>=6.7,<7.0",          # PDF form filling (BSD, pure Python)
    "PyPDFForm>=4.7,<5.0",      # Specialized PDF form API (MIT, pure Python)
    "docxtpl>=0.20,<1.0",       # Jinja2 DOCX templates (LGPL, uses python-docx + jinja2)
]
```

All libraries are pure Python, actively maintained (all released in 2026), and have permissive licenses.

---

## 5. Shared Components

### 5.1 Case Information (Collected Once, Reused Across All Tools)

The following fields are collected in Step 1 of every discovery workflow:

#### Case Identification

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `case_number` | string | Yes | e.g., "23STCV12345" |
| `court_name` | string | Yes | e.g., "Superior Court of California" |
| `court_county` | string | Yes | e.g., "Los Angeles" |
| `court_branch` | string | No | e.g., "Spring Street Courthouse" |
| `court_address` | string | No | Street address |
| `court_city_zip` | string | No | City and ZIP |
| `judge_name` | string | No | Assigned judge |
| `department` | string | No | e.g., "Dept. 34" |

#### Dates

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `complaint_filed_date` | date | Yes | Date complaint was filed |
| `trial_date` | date | No | If set, used for deadline calculations |
| `discovery_cutoff_date` | date | Auto | Calculated: trial_date - 30 days |

#### Parties

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `party_role` | enum | Yes | `plaintiff` or `defendant` |
| `plaintiffs` | list[PartyInfo] | Yes | Name(s) of plaintiff(s) |
| `defendants` | list[PartyInfo] | Yes | Name(s) of defendant(s) |
| `does_included` | bool | No | "Does 1 through 50, inclusive" |

Where `PartyInfo` is:
```
{ name: string, is_entity: bool, entity_type?: string }
```

#### Attorney Information (Propounding Party)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `attorney_name` | string | Yes* | *Or "In Pro Per" |
| `attorney_sbn` | string | Yes* | State Bar Number |
| `firm_name` | string | No | Law firm name |
| `attorney_address` | string | Yes | Street address |
| `attorney_city_state_zip` | string | Yes | City, State ZIP |
| `attorney_phone` | string | Yes | Telephone |
| `attorney_fax` | string | No | Fax number |
| `attorney_email` | string | Yes | Email address |
| `attorney_for` | string | Yes | "Plaintiff [Name]" or "Defendant [Name]" |
| `is_pro_per` | bool | No | If true, party acts as own attorney |

#### Discovery Set Information

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `set_number` | int | Yes | Set number (default: 1) |
| `propounding_party` | string | Auto | Derived from party_role |
| `responding_party` | string | Auto | Derived from party_role (opposing) |

### 5.2 Employment Claim Context (Collected Once, Drives Suggestions)

These fields determine which interrogatories, requests, and admissions are auto-suggested:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `claim_types` | list[ClaimType] | Yes | Multi-select from claim type enum |
| `employment_dates` | {start: date, end: date?} | Yes | Dates of employment |
| `is_still_employed` | bool | Yes | Affects which requests are relevant |
| `termination_type` | enum | If terminated | voluntary, involuntary, constructive |
| `protected_classes` | list[string] | If discrimination | race, sex, age, disability, religion, etc. |
| `wage_claims` | list[WageClaimType] | If wage theft | unpaid wages, overtime, breaks, misclassification |
| `adverse_actions` | list[string] | Yes | Termination, demotion, suspension, etc. |
| `filed_govt_complaint` | bool | No | CRD/DFEH/EEOC/DLSE complaint filed? |
| `govt_complaint_agency` | string | If filed | Which agency |

#### ClaimType Enum

```python
class ClaimType(str, Enum):
    FEHA_DISCRIMINATION = "feha_discrimination"
    FEHA_HARASSMENT = "feha_harassment"
    FEHA_RETALIATION = "feha_retaliation"
    FEHA_FAILURE_TO_PREVENT = "feha_failure_to_prevent"
    FEHA_FAILURE_TO_ACCOMMODATE = "feha_failure_to_accommodate"
    FEHA_FAILURE_INTERACTIVE_PROCESS = "feha_failure_interactive_process"
    WRONGFUL_TERMINATION_PUBLIC_POLICY = "wrongful_termination_public_policy"
    BREACH_IMPLIED_CONTRACT = "breach_implied_contract"
    BREACH_COVENANT_GOOD_FAITH = "breach_covenant_good_faith"
    WAGE_THEFT = "wage_theft"
    MEAL_REST_BREAK = "meal_rest_break"
    OVERTIME = "overtime"
    MISCLASSIFICATION = "misclassification"
    WHISTLEBLOWER_RETALIATION = "whistleblower_retaliation"
    LABOR_CODE_RETALIATION = "labor_code_retaliation"
    CFRA_FMLA = "cfra_fmla"
    DEFAMATION = "defamation"
    IIED = "intentional_infliction_emotional_distress"
    NIED = "negligent_infliction_emotional_distress"
    PAGA = "paga"
    UNFAIR_BUSINESS_PRACTICES = "unfair_business_practices"
```

### 5.3 Claim-to-Discovery Mapping

This is the core intelligence layer. Each claim type maps to suggested discovery items:

```python
CLAIM_DISCOVERY_MAP: dict[ClaimType, DiscoverySuggestions] = {
    ClaimType.FEHA_DISCRIMINATION: DiscoverySuggestions(
        disc001_sections=[1.1, 2.1, 2.2, 2.3, 2.5, 4.1, 6.1, 6.2, 6.3, 6.4,
                          8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.1, 9.2,
                          12.1, 12.2, 12.3, 12.6, 14.1, 15.1, 17.1],
        disc002_sections=[200.1, 200.2, 200.3, 200.4, 200.5,
                          201.1, 201.3, 202.1, 202.2,
                          207.1, 208.1, 209.1,
                          210.1, 210.2, 210.3, 210.4, 210.5,
                          212.1, 213.1, 214.1, 215.1, 216.1],
        srog_categories=["employment_relationship", "adverse_action",
                         "comparator_treatment", "decision_makers",
                         "investigation", "policies", "damages"],
        rfpd_categories=["personnel_file", "performance_reviews",
                         "discipline_records", "policies_handbooks",
                         "communications", "investigation_docs",
                         "comparator_docs", "training_records",
                         "org_charts", "job_descriptions"],
        rfa_categories=["employment_facts", "adverse_action_facts",
                        "policy_facts", "document_genuineness"],
    ),
    # ... similar mappings for each ClaimType
}
```

---

## 6. Tool 1: Form Interrogatories General (FROGs — DISC-001)

### Overview

DISC-001 is the Judicial Council's general-purpose form interrogatories. In employment cases, it's used **alongside** DISC-002. It covers background information, insurance, damages, investigation, and contentions.

**Output**: Filled editable PDF (DISC-001 form with checkboxes marked).

### DISC-001 Section Map

| Section | Title | # Interrogatories | Employment Relevance |
|---------|-------|--------------------|---------------------|
| 1.0 | Identity of Persons Answering | 1 | Always |
| 2.0 | General Background — Individual | 7 | Always (if individual party) |
| 3.0 | General Background — Business Entity | 1 | Always (if entity party) |
| 4.0 | Insurance | 2 | Always |
| 5.0 | [Reserved] | 0 | N/A |
| 6.0 | Physical, Mental, or Emotional Injuries | 7 | If emotional distress / physical injury claimed |
| 7.0 | Property Damage | 3 | Rarely relevant |
| 8.0 | Loss of Income or Earning Capacity | 8 | Almost always |
| 9.0 | Other Damages | 2 | If additional damages claimed |
| 10.0 | Medical History | 3 | If emotional distress claimed |
| 11.0 | Other Claims and Previous Claims | 2 | Always (10-year lookback) |
| 12.0 | Investigation — General | 7 | Always |
| 13.0 | Investigation — Surveillance | 2 | Standard |
| 14.0 | Statutory or Regulatory Violations | 1 | Always in employment |
| 15.0 | Denials and Special/Affirmative Defenses | 1 | Always |
| 16.0 | Defendant's Contentions — Personal Injury | 10 | If defendant |
| 17.0 | Responses to Request for Admissions | 1 | If RFAs also propounded |

### Workflow Steps

1. **Case Info** (shared) — pre-filled if already entered
2. **Claim Context** (shared) — drives auto-suggestions
3. **Section Selection** — Checkboxes grouped by section. Auto-suggested sections are pre-checked based on claim types. Attorney can check/uncheck any.
4. **Review** — Summary of all selected interrogatories
5. **Generate** — Fill DISC-001 PDF with checkboxes and header info, download

### Auto-Suggestion Logic

```python
def suggest_disc001_sections(
    claim_types: list[ClaimType],
    party_role: PartyRole,
    has_rfas: bool = False,
) -> list[float]:
    """Return list of DISC-001 section numbers to pre-check."""
    sections = {1.1, 4.1}  # Always include

    for claim in claim_types:
        sections.update(CLAIM_DISCOVERY_MAP[claim].disc001_sections)

    # Party-role-specific
    if party_role == PartyRole.PLAINTIFF:
        sections.discard(16.1)  # Defendant's contentions - not for plaintiff
        # ... remove other defendant-only sections
    elif party_role == PartyRole.DEFENDANT:
        sections.update({15.1, 16.1, 16.2, ...})

    # Conditional
    if has_rfas:
        sections.add(17.1)

    return sorted(sections)
```

---

## 7. Tool 2: Form Interrogatories Employment (FROGs — DISC-002)

### Overview

DISC-002 is the employment-specific form interrogatories. It's the single most efficient discovery tool in employment cases because form interrogatories have **no numeric limit**.

**Output**: Filled editable PDF (DISC-002 form with checkboxes marked).

### DISC-002 Section Map

| Section | Title | # Interrogatories | Directed To |
|---------|-------|--------------------|-------------|
| 200.0 | Contract Formation / Employment Relationship | 6 | Both |
| 201.0 | Adverse Employment Action | 7 | Employer |
| 202.0 | Discrimination | 2 | Employee |
| 203.0 | Harassment | 1 | Employee |
| 204.0 | Disability Discrimination | 7 | Both |
| 205.0 | Discharge in Violation of Public Policy | 1 | Both |
| 206.0 | Defamation | 3 | Both |
| 207.0 | Internal Complaints | 2 | Both |
| 208.0 | Governmental Complaints | 2 | Both |
| 209.0 | Other Employment Claims | 2 | Both |
| 210.0 | Loss of Income — to Employee | 6 | Employee |
| 211.0 | Loss of Income — to Employer | 3 | Employer |
| 212.0 | Physical/Mental/Emotional Injuries — to Employee | 7 | Employee |
| 213.0 | Other Damages — to Employee | 2 | Employee |
| 214.0 | Insurance | 2 | Both |
| 215.0 | Investigation | 2 | Both |
| 216.0 | Denials and Defenses | 1 | Both |
| 217.0 | Response to Request for Admissions | 1 | Both |

### Directional Filtering

DISC-002 sections are **directional** — some are "Interrogatories to Employee" and others are "Interrogatories to Employer." The workflow must filter based on party role:

```python
def suggest_disc002_sections(
    claim_types: list[ClaimType],
    party_role: PartyRole,  # Who is PROPOUNDING
    has_rfas: bool = False,
) -> list[float]:
    # If plaintiff is propounding → directed to defendant (employer)
    # If defendant is propounding → directed to plaintiff (employee)
    target = "employer" if party_role == PartyRole.PLAINTIFF else "employee"

    sections = set()
    for claim in claim_types:
        sections.update(CLAIM_DISCOVERY_MAP[claim].disc002_sections)

    # Filter to sections appropriate for the target
    if target == "employer":
        # Employer-directed sections
        sections &= {200.1, 200.2, 200.3, 200.4, 200.5, 200.6,
                      201.1, 201.2, 201.3, 201.4, 201.5, 201.6, 201.7,
                      205.1, 206.1, 206.2, 206.3,
                      207.1, 207.2, 208.1, 208.2, 209.1, 209.2,
                      211.1, 211.2, 211.3,
                      214.1, 214.2, 215.1, 215.2, 216.1, 217.1}
    else:
        # Employee-directed sections
        sections &= {200.1, 200.2, 200.3, 200.4, 200.5, 200.6,
                      202.1, 202.2, 203.1,
                      204.1, 204.2, 204.3, 204.4, 204.5, 204.6, 204.7,
                      205.1, 206.1, 206.2, 206.3,
                      207.1, 207.2, 208.1, 208.2, 209.1, 209.2,
                      210.1, 210.2, 210.3, 210.4, 210.5, 210.6,
                      212.1, 212.2, 212.3, 212.4, 212.5, 212.6, 212.7,
                      213.1, 213.2,
                      214.1, 214.2, 215.1, 215.2, 216.1, 217.1}

    return sorted(sections)
```

### Workflow Steps

Same 5-step pattern as DISC-001. Attorney sees sections organized by topic with plain-English descriptions alongside the formal interrogatory numbers.

---

## 8. Tool 3: Special Interrogatories (SROGs)

### Overview

SROGs are custom-drafted interrogatories on pleading paper. Limited to 35 without a declaration of necessity. Each must be a single, non-compound question. No subparts.

**Output**: Editable Word document (.docx) on 28-line pleading paper.

### SROG Categories and Bank

We maintain a **bank of employment-specific special interrogatories** organized by category. The attorney selects categories, then selects/edits individual interrogatories.

#### Category: Employment Relationship
1. State YOUR contention as to the date on which EMPLOYEE's EMPLOYMENT began.
2. IDENTIFY each job title held by EMPLOYEE during the EMPLOYMENT.
3. IDENTIFY each supervisor of EMPLOYEE during the EMPLOYMENT, including dates of supervision.
4. State each location at which EMPLOYEE performed work during the EMPLOYMENT.
5. IDENTIFY each written employment agreement between YOU and EMPLOYEE.

#### Category: Adverse Employment Action
6. State each and every reason for the TERMINATION of EMPLOYEE.
7. IDENTIFY each PERSON who participated in the decision to terminate EMPLOYEE's EMPLOYMENT.
8. IDENTIFY each PERSON who provided information relied upon in making the decision to terminate EMPLOYEE.
9. State the date on which the decision to terminate EMPLOYEE was first made or discussed.
10. IDENTIFY all DOCUMENTS reviewed or relied upon in making the decision to terminate EMPLOYEE.
11. State whether any alternative to TERMINATION was considered, and if so, describe each alternative and the reason it was rejected.

#### Category: Discrimination / Comparators
12. IDENTIFY each employee who held the same or similar position as EMPLOYEE during the EMPLOYMENT.
13. For each employee identified in response to the preceding interrogatory, state whether that employee was subject to any disciplinary action, and if so, describe each action.
14. IDENTIFY each employee who was promoted to or hired for the position formerly held by EMPLOYEE after the TERMINATION.
15. IDENTIFY each employee outside EMPLOYEE's protected class who engaged in conduct similar to that attributed to EMPLOYEE and state what action, if any, was taken against that employee.

#### Category: Harassment
16. IDENTIFY each PERSON who EMPLOYEE contends engaged in harassment.
17. For each PERSON identified in response to the preceding interrogatory, describe each act of harassment and the date on which it occurred.
18. State whether any complaints of harassment were made by employees other than EMPLOYEE regarding the same PERSON(S), and if so, IDENTIFY each complaint.

#### Category: Retaliation / Whistleblower
19. IDENTIFY each complaint, report, or disclosure made by EMPLOYEE to any PERSON regarding any violation of law, rule, or regulation.
20. State the date and substance of each protected activity EMPLOYEE contends led to the ADVERSE EMPLOYMENT ACTION.
21. IDENTIFY each PERSON who was aware of EMPLOYEE's protected activity prior to the ADVERSE EMPLOYMENT ACTION.

#### Category: Investigation
22. State whether YOU conducted an investigation in response to EMPLOYEE's complaint, and if so, describe the scope, methods, and conclusions of each investigation.
23. IDENTIFY each PERSON who conducted or participated in the investigation of EMPLOYEE's complaint.
24. IDENTIFY all DOCUMENTS generated during or as a result of the investigation.

#### Category: Policies
25. IDENTIFY each policy, procedure, or guideline in effect during the EMPLOYMENT that pertains to the claims alleged in the PLEADINGS.
26. State how each policy identified in response to the preceding interrogatory was communicated to employees.
27. IDENTIFY each training program regarding discrimination, harassment, or retaliation conducted during the EMPLOYMENT.

#### Category: Damages
28. State each item of economic damage EMPLOYEE claims to have suffered as a result of the ADVERSE EMPLOYMENT ACTION.
29. State each item of non-economic damage EMPLOYEE claims to have suffered.
30. IDENTIFY each HEALTH CARE PROVIDER who has treated EMPLOYEE for conditions attributed to the ADVERSE EMPLOYMENT ACTION.
31. State whether EMPLOYEE contends that EMPLOYER acted with malice, oppression, or fraud, and if so, state all facts supporting that contention.

#### Category: Wages / Hours
32. State the hourly rate of pay and overtime rate applicable to EMPLOYEE during each period of the EMPLOYMENT.
33. IDENTIFY all records reflecting hours worked by EMPLOYEE during the EMPLOYMENT.
34. State whether EMPLOYEE was classified as exempt from overtime, and if so, identify the exemption and all facts supporting the classification.
35. State each meal period and rest period policy applicable to EMPLOYEE during the EMPLOYMENT.

### 35-Interrogatory Counter

The UI must prominently display:
```
┌─────────────────────────────────┐
│  SROGs Selected: 23 / 35       │
│  ████████████████░░░░░  (66%)  │
│                                 │
│  ℹ 35 without declaration.     │
│  If you need more, we'll       │
│  generate the declaration.     │
└─────────────────────────────────┘
```

If count exceeds 35, auto-generate CCP 2030.050 Declaration of Necessity as an additional page.

### Workflow Steps

1. **Case Info** (shared)
2. **Claim Context** (shared) — drives category suggestions
3. **Category Selection** — Select relevant SROG categories; auto-suggested based on claims
4. **Interrogatory Selection & Editing** — Within each category, select/deselect individual SROGs. Edit text inline. Add custom interrogatories. 35-counter visible at all times.
5. **Definitions Review** — Standard definitions pre-populated, editable
6. **Review** — Full document preview with line numbers
7. **Generate** — Download .docx on pleading paper

---

## 9. Tool 4: Requests for Production of Documents (RFPDs)

### Overview

RFPDs request the opposing party to produce documents for inspection and copying. No numeric limit. Written on pleading paper.

**Output**: Editable Word document (.docx) on 28-line pleading paper.

### RFPD Categories and Bank

#### Category: Personnel Records
1. EMPLOYEE's complete personnel file, including but not limited to all performance evaluations, disciplinary records, commendations, and employment applications.
2. All job descriptions applicable to EMPLOYEE during the EMPLOYMENT.
3. All offer letters, employment agreements, and amendments thereto between YOU and EMPLOYEE.

#### Category: Termination / Adverse Action
4. All DOCUMENTS RELATING TO the decision to terminate or take ADVERSE EMPLOYMENT ACTION against EMPLOYEE, including but not limited to memoranda, emails, meeting notes, and decision-making materials.
5. All DOCUMENTS RELATING TO any performance improvement plan, corrective action, or progressive discipline applied to EMPLOYEE.
6. All separation or severance agreements offered to or executed by EMPLOYEE.

#### Category: Policies and Handbooks
7. All employee handbooks, policy manuals, and supplements in effect during EMPLOYEE's EMPLOYMENT.
8. All anti-discrimination and anti-harassment policies in effect during EMPLOYEE's EMPLOYMENT.
9. All complaint, grievance, and reporting procedures in effect during EMPLOYEE's EMPLOYMENT.
10. All progressive discipline or corrective action policies in effect during EMPLOYEE's EMPLOYMENT.

#### Category: Investigation Documents
11. All DOCUMENTS RELATING TO any investigation conducted in response to any complaint by or about EMPLOYEE.
12. All witness statements, interview notes, and investigator reports RELATING TO any complaint by EMPLOYEE.
13. All DOCUMENTS RELATING TO the findings, conclusions, and corrective action resulting from any investigation of EMPLOYEE's complaints.

#### Category: Communications
14. All COMMUNICATIONS between EMPLOYEE and any supervisor, manager, or human resources representative CONCERNING the subject matter of this action.
15. All COMMUNICATIONS among management, supervisors, or human resources personnel CONCERNING EMPLOYEE or the ADVERSE EMPLOYMENT ACTION.
16. All electronic COMMUNICATIONS, including emails, text messages, and instant messages, RELATING TO EMPLOYEE for the period [date range].

#### Category: Comparator / Similarly Situated
17. Personnel files of employees in the same department or reporting to the same supervisor who were subject to discipline during the relevant time period. *(Note: may require protective order)*
18. All DOCUMENTS RELATING TO any other complaints of discrimination, harassment, or retaliation made against the same supervisor(s) or manager(s) identified in the PLEADINGS.

#### Category: Compensation and Wages
19. All payroll records, pay stubs, and wage statements for EMPLOYEE during the EMPLOYMENT.
20. All time records, including clock-in/clock-out data, for EMPLOYEE during the EMPLOYMENT.
21. All DOCUMENTS RELATING TO EMPLOYEE's classification as exempt or non-exempt from overtime.
22. All commission agreements, bonus plans, and calculations applicable to EMPLOYEE.
23. All benefit plan documents, enrollment records, and COBRA notices relating to EMPLOYEE.

#### Category: Training
24. All records of anti-harassment and anti-discrimination training provided to managers and supervisors during the relevant time period, as required by Government Code section 12950.1.
25. All training materials and attendance records for training programs attended by EMPLOYEE.

#### Category: Organizational
26. Organizational charts for the department(s) in which EMPLOYEE worked during the EMPLOYMENT.
27. DOCUMENTS identifying EMPLOYEE's replacement, including the replacement's job application, resume, qualifications, and compensation.

#### Category: Insurance
28. All insurance policies, including employment practices liability insurance (EPLI), that may provide coverage for the claims alleged in this action.

### Production Instructions

The RFPD template includes standard production instructions:

> 1. Produce documents as they are kept in the usual course of business, or organize and label them to correspond with the categories in the demand (CCP 2031.280).
> 2. If any document is withheld on the basis of privilege, identify the document, the privilege claimed, and the factual basis for the claim.
> 3. If a document has been lost or destroyed, identify the document, describe its contents, state when and how it was lost or destroyed, and identify all persons with knowledge of the circumstances.

### Workflow Steps

1. **Case Info** (shared)
2. **Claim Context** (shared)
3. **Category Selection** — Auto-suggested RFPD categories based on claims
4. **Request Selection & Editing** — Select/deselect individual RFPDs. Edit text. Add custom requests. Date range fields for time-bounded requests.
5. **Production Instructions** — Pre-populated standard instructions, editable
6. **Definitions Review** — Standard definitions pre-populated, editable
7. **Review** — Full preview
8. **Generate** — Download .docx

---

## 10. Tool 5: Requests for Admission (RFAs)

### Overview

RFAs are the most strategically powerful discovery tool. If not timely denied, matters are deemed admitted. Limited to 35 (for facts) without declaration; genuineness of documents is unlimited.

**Output**: DISC-020 cover sheet (filled PDF) + Attachment pleading paper (.docx).

### RFA Categories and Bank

#### Category: Employment Facts
1. Admit that EMPLOYEE was employed by EMPLOYER from [start_date] to [end_date].
2. Admit that EMPLOYEE's job title at the time of the ADVERSE EMPLOYMENT ACTION was [title].
3. Admit that EMPLOYEE reported to [supervisor_name] at the time of the ADVERSE EMPLOYMENT ACTION.
4. Admit that EMPLOYEE received a [satisfactory/exceeds expectations] performance review on [date].
5. Admit that EMPLOYEE was not subject to any disciplinary action prior to [date].

#### Category: Adverse Action Facts
6. Admit that EMPLOYEE's EMPLOYMENT was terminated on [date].
7. Admit that [decision_maker_name] made or participated in the decision to terminate EMPLOYEE.
8. Admit that no written warning was given to EMPLOYEE prior to the TERMINATION.
9. Admit that EMPLOYEE was not offered the opportunity to correct the alleged deficiency before the TERMINATION.
10. Admit that EMPLOYEE was replaced by [replacement_name].

#### Category: Complaint and Investigation Facts
11. Admit that EMPLOYEE filed a complaint of [type] with [HR/supervisor/agency] on [date].
12. Admit that YOU received EMPLOYEE's complaint on or about [date].
13. Admit that no investigation was initiated in response to EMPLOYEE's complaint within [X] days.
14. Admit that the investigation of EMPLOYEE's complaint was conducted by [investigator], who also reports to the supervisor accused in the complaint.

#### Category: Policy Facts
15. Admit that EMPLOYER had an anti-discrimination policy in effect on [date].
16. Admit that EMPLOYER's anti-harassment policy required supervisors to report complaints within [X] hours/days.
17. Admit that EMPLOYER failed to provide anti-harassment training as required by Government Code section 12950.1 to [supervisor_name] during [year].

#### Category: Wage and Hour Facts
18. Admit that EMPLOYEE's regular hourly rate of pay was $[amount] during [time period].
19. Admit that EMPLOYEE worked in excess of [8 hours per day / 40 hours per week] during [specific dates].
20. Admit that EMPLOYEE was not provided a meal period of at least 30 minutes for shifts exceeding 5 hours on [specific dates].

#### Category: Document Genuineness (No Limit)
21. Admit that the document attached as Exhibit A is a true and correct copy of [description].
22. Admit that the document attached as Exhibit B is a true and correct copy of EMPLOYEE's termination letter dated [date].
23. Admit that the document attached as Exhibit C is a true and correct copy of the employee handbook in effect on [date].

### 35-Counter (Facts Only)

The UI tracks fact-based RFAs separately from genuineness-of-document RFAs:

```
┌──────────────────────────────────────┐
│  Fact RFAs: 18 / 35                  │
│  █████████████░░░░░░░░░░  (51%)     │
│                                      │
│  Document Genuineness RFAs: 5        │
│  (no limit)                          │
└──────────────────────────────────────┘
```

### Workflow Steps

1. **Case Info** (shared)
2. **Claim Context** (shared)
3. **RFA Type Selection** — Truth of facts, genuineness of documents, or both
4. **Category Selection & Editing** — Select categories, edit individual RFAs. Fill in bracketed placeholders with case-specific facts. Counter visible.
5. **Document Exhibits** — For genuineness RFAs: label each exhibit (A, B, C...). User will attach hard copies separately.
6. **Definitions Review** — Standard definitions
7. **Review** — Preview DISC-020 cover + attachment
8. **Generate** — Download DISC-020 PDF + attachment .docx

---

## 11. Data Schema

### Backend Models (Python)

```python
# src/employee_help/discovery/models.py

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

class PartyRole(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"

class DiscoveryToolType(str, Enum):
    FROGS_GENERAL = "frogs_general"      # DISC-001
    FROGS_EMPLOYMENT = "frogs_employment" # DISC-002
    SROGS = "srogs"                       # Special Interrogatories
    RFPDS = "rfpds"                       # Request for Production
    RFAS = "rfas"                         # Request for Admission

class ClaimType(str, Enum):
    # ... (see Section 5.2 above)

class WageClaimType(str, Enum):
    UNPAID_WAGES = "unpaid_wages"
    OVERTIME = "overtime"
    MEAL_BREAKS = "meal_breaks"
    REST_BREAKS = "rest_breaks"
    MISCLASSIFICATION = "misclassification"
    WAITING_TIME = "waiting_time"
    WAGE_STATEMENT = "wage_statement"

@dataclass(frozen=True)
class PartyInfo:
    name: str
    is_entity: bool = False
    entity_type: str | None = None  # "corporation", "llc", "partnership", etc.

@dataclass(frozen=True)
class AttorneyInfo:
    name: str
    sbn: str
    address: str
    city_state_zip: str
    phone: str
    email: str
    firm_name: str | None = None
    fax: str | None = None
    is_pro_per: bool = False
    attorney_for: str = ""  # "Plaintiff Jane Doe"

@dataclass(frozen=True)
class CaseInfo:
    case_number: str
    court_county: str
    court_name: str = "Superior Court of California"
    court_branch: str | None = None
    court_address: str | None = None
    court_city_zip: str | None = None
    judge_name: str | None = None
    department: str | None = None
    complaint_filed_date: date | None = None
    trial_date: date | None = None
    party_role: PartyRole = PartyRole.PLAINTIFF
    plaintiffs: tuple[PartyInfo, ...] = ()
    defendants: tuple[PartyInfo, ...] = ()
    does_included: bool = True
    attorney: AttorneyInfo | None = None
    set_number: int = 1

@dataclass(frozen=True)
class ClaimContext:
    claim_types: tuple[ClaimType, ...]
    employment_start_date: date
    employment_end_date: date | None = None
    is_still_employed: bool = False
    termination_type: str | None = None
    protected_classes: tuple[str, ...] = ()
    wage_claims: tuple[WageClaimType, ...] = ()
    adverse_actions: tuple[str, ...] = ()
    filed_govt_complaint: bool = False
    govt_complaint_agency: str | None = None

@dataclass(frozen=True)
class DiscoveryRequest:
    """A single interrogatory, request for production, or request for admission."""
    id: str                         # Unique ID (e.g., "srog_employment_001")
    text: str                       # Full text of the request
    category: str                   # Category slug
    is_selected: bool = True        # Whether included in output
    is_custom: bool = False         # User-added (not from bank)
    order: int = 0                  # Display/output order
    notes: str | None = None        # Internal notes (not in output)

@dataclass
class DiscoverySession:
    """Complete state for a discovery workflow session."""
    id: str                                     # UUID
    tool_type: DiscoveryToolType
    case_info: CaseInfo
    claim_context: ClaimContext
    requests: list[DiscoveryRequest] = field(default_factory=list)
    definitions: dict[str, str] = field(default_factory=dict)
    production_instructions: str | None = None  # RFPDs only
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    generated_at: datetime | None = None
```

### Database Schema (SQLite — for future persistence)

```sql
-- Discovery sessions (future: when attorneys have accounts)
CREATE TABLE IF NOT EXISTS discovery_sessions (
    id TEXT PRIMARY KEY,                     -- UUID
    tool_type TEXT NOT NULL,                 -- frogs_general, srogs, rfpds, rfas
    case_info_json TEXT NOT NULL,            -- JSON blob of CaseInfo
    claim_context_json TEXT NOT NULL,        -- JSON blob of ClaimContext
    requests_json TEXT NOT NULL,             -- JSON array of DiscoveryRequest
    definitions_json TEXT,                   -- JSON dict of definitions
    production_instructions TEXT,            -- RFPD production instructions
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    generated_at TEXT,                       -- When document was last generated
    -- Future: organization/user ownership
    organization_id TEXT,                    -- FK to organizations table (future)
    user_id TEXT,                            -- FK to users table (future)
    case_number TEXT GENERATED ALWAYS AS (json_extract(case_info_json, '$.case_number')) STORED
);

CREATE INDEX IF NOT EXISTS idx_sessions_case ON discovery_sessions(case_number);
CREATE INDEX IF NOT EXISTS idx_sessions_org ON discovery_sessions(organization_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tool ON discovery_sessions(tool_type);

-- Audit log for generated documents (future: billing)
CREATE TABLE IF NOT EXISTS discovery_generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES discovery_sessions(id),
    tool_type TEXT NOT NULL,
    output_format TEXT NOT NULL,             -- "pdf" or "docx"
    request_count INTEGER NOT NULL,          -- Number of requests in document
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    ip_address TEXT,
    user_agent TEXT
);
```

### API Schema (Pydantic)

```python
# src/employee_help/api/schemas.py — additions

class DiscoveryGenerateRequest(BaseModel):
    tool_type: DiscoveryToolType
    case_info: CaseInfoSchema
    claim_context: ClaimContextSchema
    selected_sections: list[float] | None = None    # FROGs only
    requests: list[DiscoveryRequestSchema] | None = None  # SROGs/RFPDs/RFAs
    definitions: dict[str, str] | None = None
    production_instructions: str | None = None

class DiscoverySuggestRequest(BaseModel):
    tool_type: DiscoveryToolType
    claim_types: list[ClaimType]
    party_role: PartyRole

class DiscoverySuggestResponse(BaseModel):
    suggested_sections: list[float] | None = None      # FROGs
    suggested_requests: list[DiscoveryRequestSchema] | None = None  # SROGs/RFPDs/RFAs
    categories: list[CategorySchema]
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/discovery/suggest` | Get auto-suggested sections/requests based on claims |
| POST | `/api/discovery/generate` | Generate document (returns file download) |
| GET | `/api/discovery/banks/{tool_type}` | Get full request bank for a tool |
| GET | `/api/discovery/definitions` | Get standard definitions |

---

## 12. Document Generation Engine

### 12.1 PDF Filling (DISC-001, DISC-002, DISC-020)

**Library**: `pypdf` (primary) + `PyPDFForm` (fallback)

```python
# src/employee_help/discovery/generator/pdf_filler.py

from pypdf import PdfReader, PdfWriter

def fill_disc_form(
    template_path: str,
    case_info: CaseInfo,
    selected_sections: list[float],
) -> bytes:
    """Fill a DISC-001 or DISC-002 PDF form.

    Returns bytes of the filled PDF (still editable).
    """
    reader = PdfReader(template_path)
    writer = PdfWriter()
    writer.append(reader)

    # Get field names and states
    fields = reader.get_fields()

    # Build field value map
    values = {}

    # Header fields
    values["attorney_name"] = case_info.attorney.name if case_info.attorney else ""
    values["sbn"] = case_info.attorney.sbn if case_info.attorney else ""
    values["court_county"] = case_info.court_county
    values["case_number"] = case_info.case_number
    values["plaintiff"] = ", ".join(p.name for p in case_info.plaintiffs)
    values["defendant"] = ", ".join(d.name for d in case_info.defendants)
    values["asking_party"] = _propounding_party_name(case_info)
    values["answering_party"] = _responding_party_name(case_info)
    values["set_number"] = str(case_info.set_number)

    # Checkbox fields — mark selected sections
    for section in selected_sections:
        checkbox_field = _section_to_field_name(section, fields)
        if checkbox_field:
            values[checkbox_field] = True  # PyPDFForm uses boolean

    # Fill form (keep editable — do NOT flatten)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values, auto_regenerate=False)

    # Set NeedAppearances flag so readers regenerate field appearances
    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update({
            "/NeedAppearances": True
        })

    import io
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
```

**Implementation Step 1**: Download official PDFs, inspect field names:
```python
reader = PdfReader("disc001.pdf")
for name, field in reader.get_fields().items():
    print(f"{name}: type={field.get('/FT')}, states={field.get('/_States_')}")
```

### 12.2 DOCX Generation (SROGs, RFPDs, RFAs)

**Library**: `docxtpl` (Jinja2 templates)

**Template approach**: Create Word templates with correct California pleading paper formatting (28-line, line numbers, margins) in Microsoft Word. Use Jinja2 tags for dynamic content.

```python
# src/employee_help/discovery/generator/docx_builder.py

from docxtpl import DocxTemplate

def generate_srog_document(
    template_path: str,
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
    definitions: dict[str, str],
) -> bytes:
    """Generate special interrogatories on pleading paper.

    Returns bytes of the DOCX file.
    """
    doc = DocxTemplate(template_path)

    # Build context
    context = {
        # Attorney block
        "attorney_name": case_info.attorney.name,
        "attorney_sbn": case_info.attorney.sbn,
        "firm_name": case_info.attorney.firm_name or "",
        "attorney_address": case_info.attorney.address,
        "attorney_city_state_zip": case_info.attorney.city_state_zip,
        "attorney_phone": case_info.attorney.phone,
        "attorney_fax": case_info.attorney.fax or "",
        "attorney_email": case_info.attorney.email,
        "attorney_for": case_info.attorney.attorney_for,
        "is_pro_per": case_info.attorney.is_pro_per,

        # Court block
        "court_name": case_info.court_name,
        "court_county": case_info.court_county,
        "court_branch": case_info.court_branch or "",

        # Case caption
        "plaintiffs": [p.name for p in case_info.plaintiffs],
        "defendants": [d.name for d in case_info.defendants],
        "does_included": case_info.does_included,
        "case_number": case_info.case_number,

        # Discovery info
        "document_title": f"{_propounding_party_name(case_info).upper()}'S "
                         f"SPECIAL INTERROGATORIES TO "
                         f"{_responding_party_name(case_info).upper()}",
        "set_number": case_info.set_number,
        "propounding_party": _propounding_party_name(case_info),
        "responding_party": _responding_party_name(case_info),

        # Definitions
        "definitions": definitions,

        # Interrogatories
        "requests": [
            {"number": i + 1, "text": r.text}
            for i, r in enumerate(sorted(
                [r for r in requests if r.is_selected],
                key=lambda r: r.order
            ))
        ],

        # Metadata
        "total_count": sum(1 for r in requests if r.is_selected),
        "exceeds_35": sum(1 for r in requests if r.is_selected) > 35,
    }

    doc.render(context)

    import io
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
```

### California Pleading Paper Format (CRC Rules 2.100-2.111)

| Requirement | Value |
|-------------|-------|
| Paper size | 8.5" x 11" |
| Font | Times New Roman 12pt or Courier 12pt |
| Line spacing | Double-spaced (24pt) |
| Left margin | 1 inch (after line numbers) |
| Right margin | 0.5 inch minimum |
| Top margin | ~0.5 inch |
| Bottom margin | ~0.5 inch (above page number) |
| Line numbers | 1-28 per page, left margin, consecutive |
| Page numbers | Centered bottom, Arabic numerals |
| Lines per page | 28 |

The DOCX templates will be pre-formatted in Word with these specifications. `docxtpl` preserves all formatting including line numbering (which is a section property in OOXML).

---

## 13. UI/UX Design

### 13.1 Design Philosophy

**Framework**: Multi-step wizard (not accordion, not tabs).

**Why wizard over accordion/tabs**:
- Attorneys need to move through steps sequentially — case info before claim context before request selection
- Wizard provides clear progress indication (Krug: "Where am I?")
- Reduces cognitive overload — only one decision-set visible at a time (Refactoring UI: start with too much white space)
- Each step is "mindless and unambiguous" (Krug's Second Law)
- Accordion would expose 100+ checkboxes simultaneously; tabs would hide critical state

**Why not dumbed down**:
- Touch targets remain 44px minimum, but information density is higher than consumer tools
- Labels use legal terminology (with tooltips for less common terms)
- Power features: bulk select/deselect per category, "Select All Standard" presets
- Keyboard navigation for rapid checkbox toggling

### 13.2 Wizard Step Indicator

A persistent horizontal step bar at the top of the workflow:

```
  ┌─────────────────────────────────────────────────────┐
  │  ● Case Info  ─── ● Claims  ─── ○ Select  ─── ○ Review  ─── ○ Generate │
  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  │                              Step 2 of 5                      │
  └─────────────────────────────────────────────────────┘
```

- Filled circles (●) = completed steps (clickable to go back)
- Current step highlighted with accent color
- Empty circles (○) = future steps (not clickable)
- Progress bar fills proportionally
- Compact on mobile: step numbers only, no labels

**Tailwind implementation**:
```
<div className="flex items-center gap-2 px-4 py-3 border-b border-border">
  {steps.map((step, i) => (
    <>
      <button
        className={`flex items-center gap-1.5 text-sm font-medium
          ${i < current ? 'text-accent cursor-pointer' : ''}
          ${i === current ? 'text-text-primary' : ''}
          ${i > current ? 'text-text-tertiary cursor-default' : ''}`}
      >
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs
          ${i < current ? 'bg-accent text-white' : ''}
          ${i === current ? 'bg-accent text-white' : ''}
          ${i > current ? 'bg-surface-raised text-text-tertiary border border-border' : ''}`}>
          {i < current ? '✓' : i + 1}
        </span>
        <span className="hidden sm:inline">{step.label}</span>
      </button>
      {i < steps.length - 1 && (
        <div className={`flex-1 h-0.5 ${i < current ? 'bg-accent' : 'bg-border'}`} />
      )}
    </>
  ))}
</div>
```

### 13.3 Navigation

Persistent bottom bar (matching app's fixed-bottom pattern):

```
┌──────────────────────────────────────────────┐
│                                              │
│   [← Back]                    [Next Step →]  │
│                                              │
└──────────────────────────────────────────────┘
```

- "Back" = ghost button (secondary action)
- "Next Step" = solid accent button (primary action)
- Final step: "Next Step" becomes "Generate & Download"
- Disabled state when validation fails (with inline error messages)

### 13.4 Case Info Form (Step 1)

Two-column layout on desktop (attorney info left, case info right). Single column on mobile.

Sections separated by clear headings with more space above than below (Gestalt proximity):

```
ATTORNEY INFORMATION
─────────────────────
[Name]          [SBN]
[Firm]
[Address]
[City, ST ZIP]
[Phone]         [Email]
☐ Party is self-represented (In Pro Per)

                    32px gap

CASE INFORMATION
─────────────────
[Case Number]      [Set Number: 1]
[Court County ▼]   [Branch]
[Judge]            [Department]

                    32px gap

PARTIES
─────────────
○ I am the Plaintiff    ○ I am the Defendant

Plaintiff(s):
  [Name]  ☐ Entity  [+ Add Plaintiff]
Defendant(s):
  [Name]  ☐ Entity  [+ Add Defendant]
  ☐ Include "Does 1-50"

                    32px gap

KEY DATES
─────────────
[Complaint Filed]  [Trial Date (optional)]
```

**Smart defaults**:
- Set Number defaults to 1
- Court Name defaults to "Superior Court of California"
- "Does 1-50" checked by default
- If trial date entered, auto-calculate and display discovery cutoff

### 13.5 Claim Context (Step 2)

Multi-select chips for claim types, organized by category:

```
What claims are at issue? (Select all that apply)

DISCRIMINATION & HARASSMENT
  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
  │ ☑ FEHA Discrim.  │ │ ☑ FEHA Harassment│ │ ☐ FEHA Retaliation   │
  └──────────────────┘ └──────────────────┘ └──────────────────────┘
  ┌──────────────────────────┐ ┌──────────────────────────────────┐
  │ ☐ Failure to Accommodate │ │ ☐ Failure to Engage Interactive  │
  └──────────────────────────┘ └──────────────────────────────────┘

WRONGFUL TERMINATION
  ┌────────────────────────────┐ ┌──────────────────────────┐
  │ ☐ WT - Public Policy       │ │ ☐ Breach Implied Contract│
  └────────────────────────────┘ └──────────────────────────┘

WAGE & HOUR
  ┌──────────────┐ ┌─────────────────┐ ┌──────────┐ ┌──────────────────┐
  │ ☐ Wage Theft │ │ ☐ Meal/Rest Brk │ │ ☐ OT     │ │ ☐ Misclassify    │
  └──────────────┘ └─────────────────┘ └──────────┘ └──────────────────┘

RETALIATION & WHISTLEBLOWER
  ┌──────────────────────────┐ ┌──────────────────────┐
  │ ☐ Whistleblower (LC 1102)│ │ ☐ Labor Code Retaliat│
  └──────────────────────────┘ └──────────────────────┘

OTHER
  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ ☐ CFRA   │ │ ☐ Defam. │ │ ☐ IIED   │ │ ☐ PAGA   │
  └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

Below claims, conditional fields appear:

```
If discrimination selected:
  Protected class(es):  ☑ Race  ☐ Sex  ☑ Age  ☐ Disability  ☐ Religion  ...

Employment dates:
  [Start Date]  [End Date or ☐ Still Employed]

If terminated:
  ○ Involuntary  ○ Voluntary  ○ Constructive

Government complaint filed?
  ○ Yes → [Agency: CRD / EEOC / DLSE / other]
  ○ No
```

### 13.6 Request Selection (Step 3) — The Core UX Challenge

This step varies by tool type but follows a common pattern:

#### For FROGs (DISC-001 / DISC-002): Category-Based Checkbox Tree

```
┌─────────────────────────────────────────────────────┐
│  ☑ Select All Suggested  │  ☐ Select All  │  Clear  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ▼ Section 1.0 — Identity (1 interrogatory)    ☑   │
│    ☑ 1.1 Identity of persons preparing responses    │
│                                                     │
│  ▼ Section 2.0 — Background (7 interrogatories) ☑  │
│    ☑ 2.1 Full name and aliases                      │
│    ☑ 2.2 Date of birth                              │
│    ☑ 2.3 Addresses (past 5 years)                   │
│    ☑ 2.5 Education                                  │
│    ☐ 2.6 Driver's license                           │
│    ☐ 2.7 Felony convictions                         │
│                                                     │
│  ▶ Section 4.0 — Insurance (2)                 ☑   │
│  ▶ Section 6.0 — Injuries (7)                 ☑    │
│  ▶ Section 8.0 — Loss of Income (8)           ☑    │
│  ▶ Section 12.0 — Investigation (7)           ☑    │
│  ▶ Section 14.0 — Statutory Violations (1)    ☑    │
│  ▶ Section 15.0 — Denials & Defenses (1)      ☑    │
│                                                     │
│  ▶ Section 7.0 — Property Damage (3)          ☐    │
│  ▶ Section 10.0 — Medical History (3)         ☐    │
│  ▶ Section 16.0 — Def. Contentions (10)       ☐    │
│                                                     │
│  ── Not suggested (click to expand) ──              │
│  ▶ Section 3.0 — Business Entity (1)          ☐    │
│  ▶ Section 11.0 — Other Claims (2)            ☐    │
│  ▶ Section 13.0 — Surveillance (2)            ☐    │
│                                                     │
│  Total selected: 34 interrogatories                 │
└─────────────────────────────────────────────────────┘
```

- **Suggested sections**: Pre-expanded and pre-checked at top, sorted by relevance
- **Non-suggested sections**: Collapsed at bottom under "Not suggested" divider
- **Section-level checkbox**: Toggles all interrogatories in section
- **Collapsible sections**: Click to expand and see individual interrogatories
- **Tooltips**: Hover on interrogatory number to see full text

#### For SROGs / RFPDs / RFAs: Category Card Grid + Editor

```
┌────────────────────────────────────────────────────────────┐
│  Categories (select to add requests)          SROGs: 23/35 │
│  ████████████████████░░░░░░░░  (66%)                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────────────┐  ┌─────────────────────┐         │
│  │ ☑ Employment Rel.   │  │ ☑ Adverse Action     │         │
│  │    5 interrogatories │  │    6 interrogatories │         │
│  │    ★ Suggested       │  │    ★ Suggested       │         │
│  └─────────────────────┘  └─────────────────────┘         │
│  ┌─────────────────────┐  ┌─────────────────────┐         │
│  │ ☑ Discrimination    │  │ ☐ Harassment         │         │
│  │    4 interrogatories │  │    3 interrogatories │         │
│  │    ★ Suggested       │  │                      │         │
│  └─────────────────────┘  └─────────────────────┘         │
│  ... more categories ...                                   │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  Selected Requests (drag to reorder)                       │
│                                                            │
│  1. ☑ State YOUR contention as to the date on which        │
│       EMPLOYEE's EMPLOYMENT began.             [Edit] [✕]  │
│                                                            │
│  2. ☑ IDENTIFY each job title held by EMPLOYEE during      │
│       the EMPLOYMENT.                          [Edit] [✕]  │
│                                                            │
│  3. ☑ IDENTIFY each supervisor of EMPLOYEE during the      │
│       EMPLOYMENT, including dates...           [Edit] [✕]  │
│                                                            │
│  ... more requests ...                                     │
│                                                            │
│  [+ Add Custom Request]                                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

- **Category cards**: Check/uncheck to add/remove all requests in category
- **Request list**: Each request editable inline, removable, reorderable
- **Counter**: Always visible, turns yellow at 30, red at 35+
- **Add Custom**: Text input for user-written requests
- **Edit modal**: Click "Edit" opens inline editing with larger text area

### 13.7 Review (Step 4)

Full document preview rendered as styled HTML (not actual PDF/DOCX rendering):

```
┌─────────────────────────────────────────────────────────────┐
│  Document Preview                               [Edit Step] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  JOHN DOE (SBN 123456)                                     │
│  Doe Law Firm                                               │
│  123 Main Street                                            │
│  Los Angeles, CA 90001                                      │
│  (213) 555-1234 | john@doelaw.com                          │
│  Attorney for Plaintiff JANE SMITH                          │
│                                                             │
│  SUPERIOR COURT OF CALIFORNIA                               │
│  COUNTY OF LOS ANGELES                                      │
│                                                             │
│  JANE SMITH,            ) Case No. 24STCV56789             │
│       Plaintiff,        )                                   │
│  v.                     ) PLAINTIFF'S SPECIAL               │
│  ACME CORP,             ) INTERROGATORIES TO                │
│       Defendant.        ) DEFENDANT ACME CORP              │
│  ________________________) Set One                          │
│                                                             │
│  PROPOUNDING PARTY: Plaintiff JANE SMITH                    │
│  RESPONDING PARTY:  Defendant ACME CORP                     │
│  SET NUMBER:        One                                     │
│                                                             │
│  ... (rest of document preview) ...                         │
│                                                             │
│  ─────────────────────────────────────────────────          │
│  23 interrogatories | Last edited: just now                 │
│                                                             │
│  [← Back to Edit]              [Generate & Download →]      │
└─────────────────────────────────────────────────────────────┘
```

### 13.8 Mobile Considerations

- Wizard steps collapse to numbered pills (no labels)
- Case info form becomes single-column
- Request selection uses full-width cards instead of grid
- Checkbox tree uses full-width expandable sections
- Bottom navigation bar uses `env(safe-area-inset-bottom)`
- Minimum touch targets: 44px
- No hover-dependent interactions

### 13.9 Engagement Patterns (Hooked Framework)

| Phase | Implementation |
|-------|---------------|
| **Trigger** | Attorney receives new case → needs discovery set. Link from chat ("Generate discovery for this claim type") |
| **Action** | Minimal friction: Case info → Claims → Select → Download. 5 steps, ~10 minutes. |
| **Variable Reward** | Comprehensive, correctly-formatted discovery set tailored to their exact claims (Reward of Self: mastery + Reward of Hunt: thoroughness) |
| **Investment** | Case info stored for reuse across tools. Builds habit: "I always start my discovery here." |

---

## 14. Phased Implementation Plan

### Phase 5A: Foundation (Backend Schema + Document Generation Engine)

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5A.1 | Create `src/employee_help/discovery/` module with `models.py` (all dataclasses, enums) | models.py | S |
| 5A.2 | Create `case_info.py` — CaseInfo validation, serialization | case_info.py | S |
| 5A.3 | Create `definitions.py` — standard employment discovery definitions | definitions.py | S |
| 5A.4 | Add `[discovery]` dependency group to pyproject.toml (pypdf, PyPDFForm, docxtpl) | pyproject.toml | XS |
| 5A.5 | Download DISC-001, DISC-002, DISC-020 PDFs; inspect field names; create field mapping | generator/templates/, pdf_mapping.py | M |
| 5A.6 | Implement `pdf_filler.py` — fill JC PDF forms (header, checkboxes) | generator/pdf_filler.py | M |
| 5A.7 | Create pleading paper DOCX templates in Word (28-line, line numbers, margins, caption) | generator/templates/*.docx | M |
| 5A.8 | Implement `docx_builder.py` — Jinja2 DOCX rendering for SROGs/RFPDs/RFAs | generator/docx_builder.py | M |
| 5A.9 | Unit tests for PDF filling (field mapping, checkbox states, header population) | tests/test_pdf_filler.py | M |
| 5A.10 | Unit tests for DOCX generation (template rendering, content, formatting) | tests/test_docx_builder.py | M |
| **Gate 5A** | PDF fills correctly; DOCX renders on pleading paper; both are editable in their respective apps | |

### Phase 5B: Discovery Intelligence (Request Banks + Claim Mapping)

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5B.1 | Create `frogs_general.py` — DISC-001 section registry with metadata + suggestion logic | frogs_general.py | M |
| 5B.2 | Create `frogs_employment.py` — DISC-002 section registry with directional filtering | frogs_employment.py | M |
| 5B.3 | Create `srogs.py` — SROG request bank (~35 employment interrogatories by category) | srogs.py | L |
| 5B.4 | Create `rfpds.py` — RFPD request bank (~28 employment document categories) | rfpds.py | L |
| 5B.5 | Create `rfas.py` — RFA request bank (~25 employment admissions by category) | rfas.py | L |
| 5B.6 | Implement claim-to-discovery mapping (`CLAIM_DISCOVERY_MAP`) | models.py or mapping.py | L |
| 5B.7 | Unit tests: suggestion logic for each tool type across all claim types | tests/test_discovery_*.py | L |
| 5B.8 | Unit tests: 35-limit tracking for SROGs and RFAs | tests/test_discovery_limits.py | S |
| **Gate 5B** | Every ClaimType produces reasonable suggestions for all 4 tool types; limits enforced | |

### Phase 5C: API Endpoints

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5C.1 | Add discovery Pydantic schemas to `schemas.py` | api/schemas.py | M |
| 5C.2 | Create discovery router with suggest/generate/banks/definitions endpoints | api/discovery_routes.py | M |
| 5C.3 | Wire generate endpoint to PDF filler and DOCX builder | api/discovery_routes.py | M |
| 5C.4 | Return file as StreamingResponse with correct Content-Type/Content-Disposition | api/discovery_routes.py | S |
| 5C.5 | Add SQLite schema for discovery_sessions and discovery_generations (create tables, no persistence logic yet) | storage/models.py, storage/storage.py | M |
| 5C.6 | API integration tests (validation, generation, file download) | tests/test_discovery_api.py | L |
| **Gate 5C** | POST /api/discovery/generate returns correct PDF/DOCX files; all endpoints return valid responses | |

### Phase 5D: Frontend — Shared Components

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5D.1 | Create `wizard-stepper.tsx` — progress bar with step indicator | components/discovery/ | M |
| 5D.2 | Create `wizard-navigation.tsx` — Back/Next/Generate bottom bar | components/discovery/ | S |
| 5D.3 | Create `case-info-form.tsx` — all case information fields with validation | components/discovery/ | L |
| 5D.4 | Create `claim-selector.tsx` — multi-select claim chips with conditional fields | components/discovery/ | L |
| 5D.5 | Create `party-role-selector.tsx` — plaintiff/defendant toggle | components/discovery/ | S |
| 5D.6 | Create `definition-editor.tsx` — key-value editor for legal definitions | components/discovery/ | M |
| 5D.7 | Create `download-button.tsx` — trigger generation and download file | components/discovery/ | M |
| 5D.8 | Create `discovery-api.ts` — API client functions for all discovery endpoints | lib/discovery-api.ts | M |
| 5D.9 | Create client-side state management (React context or zustand for case info persistence) | lib/discovery-context.tsx | M |
| 5D.10 | Discovery tools landing page (`/tools/discovery/page.tsx`) | app/tools/discovery/ | S |
| **Gate 5D** | Shared components render, validate, and persist state across steps | |

### Phase 5E: Frontend — FROG Workflows (DISC-001 + DISC-002)

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5E.1 | Create `interrogatory-picker.tsx` — collapsible checkbox tree for FROG sections | components/discovery/ | L |
| 5E.2 | Build DISC-001 wizard page (5 steps: case info → claims → sections → review → generate) | app/tools/discovery/frogs-general/ | L |
| 5E.3 | Build DISC-002 wizard page (same pattern, directional filtering) | app/tools/discovery/frogs-employment/ | M |
| 5E.4 | Implement auto-suggestion highlighting (pre-check suggested, dim non-suggested) | interrogatory-picker.tsx | M |
| 5E.5 | Implement review/preview step (styled HTML document preview) | components/discovery/preview-panel.tsx | L |
| 5E.6 | E2E tests: complete FROG workflow from case info to download | tests/e2e/ or manual | L |
| **Gate 5E** | Attorney can complete DISC-001 and DISC-002 workflows end-to-end; downloads editable PDFs | |

### Phase 5F: Frontend — SROG, RFPD, RFA Workflows

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5F.1 | Create `request-builder.tsx` — category cards + editable request list + counter | components/discovery/ | XL |
| 5F.2 | Build SROG wizard page (7 steps: case → claims → categories → requests → definitions → review → generate) | app/tools/discovery/special-interrogatories/ | L |
| 5F.3 | Build RFPD wizard page (8 steps: adds production instructions) | app/tools/discovery/request-production/ | L |
| 5F.4 | Build RFA wizard page (8 steps: adds exhibit labeling) | app/tools/discovery/request-admission/ | L |
| 5F.5 | Implement 35-limit counter with visual warning states | request-builder.tsx | M |
| 5F.6 | Implement inline request editing (expand to textarea, save) | request-builder.tsx | M |
| 5F.7 | Implement "Add Custom Request" flow | request-builder.tsx | S |
| 5F.8 | E2E tests: complete SROG/RFPD/RFA workflows from case info to download | tests/e2e/ | L |
| **Gate 5F** | All four discovery tools functional end-to-end; downloads correct PDFs and DOCX files | |

### Phase 5G: Polish & Integration

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 5G.1 | Cross-tool case info persistence (enter once, reuse across all 4 tools) | discovery-context.tsx | M |
| 5G.2 | Declaration of Necessity auto-generation when SROGs > 35 or RFAs > 35 | srogs.py, rfas.py, docx_builder.py | M |
| 5G.3 | Discovery cutoff date calculator (trial date - 30 days, with service method extensions) | models.py, case-info-form.tsx | S |
| 5G.4 | Proof of Service form generation (POS-030 filled PDF) | pdf_filler.py | M |
| 5G.5 | Link from RAG chat: "Based on your question, you may want to generate [discovery type]" | conversation-turn.tsx, service.py | M |
| 5G.6 | Update tools index page with discovery tools | app/tools/page.tsx | S |
| 5G.7 | Accessibility audit: keyboard navigation, screen reader, color contrast | All discovery components | M |
| 5G.8 | Mobile optimization pass | All discovery components | M |
| **Gate 5G** | Feature-complete MVP: all 4 tools, cross-tool state, declarations, POS, chat integration | |

### Size Legend
- **XS**: < 1 hour
- **S**: 1-2 hours
- **M**: 2-4 hours
- **L**: 4-8 hours
- **XL**: 8+ hours

---

## 15. Testing Strategy

### Unit Tests (Pure Computation)

| Module | Test Coverage |
|--------|---------------|
| `models.py` | All enum values, dataclass serialization, validation |
| `frogs_general.py` | Suggestion logic for every ClaimType + PartyRole combination |
| `frogs_employment.py` | Directional filtering (plaintiff propounding vs defendant propounding) |
| `srogs.py` | Request bank completeness, category mapping, 35-limit enforcement |
| `rfpds.py` | Request bank completeness, category mapping |
| `rfas.py` | Request bank completeness, 35-limit for facts, genuineness unlimited |
| `definitions.py` | All standard definitions present and well-formed |
| `case_info.py` | Validation: required fields, date ranges, party role inference |

### Integration Tests (Document Generation)

| Test | Verification |
|------|-------------|
| PDF field mapping | Every checkbox in DISC-001/002 maps to a known field name |
| PDF filling | Header fields populated correctly; checkboxes in correct state |
| PDF editability | Filled PDF opens in Adobe/Preview with editable fields (not flattened) |
| DOCX rendering | Template renders with correct content; no Jinja2 artifacts |
| DOCX formatting | 28 lines per page, line numbers present, correct margins |
| DOCX editability | Generated DOCX opens in Word/LibreOffice and is fully editable |

### API Tests

| Endpoint | Tests |
|----------|-------|
| POST /api/discovery/suggest | Valid request returns suggestions; invalid claim type returns 422 |
| POST /api/discovery/generate | Valid request returns file with correct Content-Type; FROG returns PDF; SROG returns DOCX |
| GET /api/discovery/banks/{tool} | Returns complete request bank for each tool type |
| GET /api/discovery/definitions | Returns standard definitions |

### E2E Tests (Frontend)

| Flow | Steps |
|------|-------|
| DISC-001 happy path | Fill case info → select claims → select sections → review → download PDF |
| DISC-002 happy path | Same flow, verify directional filtering |
| SROG happy path | Fill case info → select claims → select categories → edit requests → definitions → review → download DOCX |
| SROG 35-limit | Add 36 requests → verify warning → verify declaration generated |
| RFPD happy path | Full flow → download DOCX |
| RFA happy path | Full flow with both fact and genuineness requests → download DISC-020 + DOCX |
| Cross-tool persistence | Complete DISC-001 → start SROG → verify case info pre-populated |
| Mobile | Complete any workflow on 375px viewport |

---

## Appendix A: Judicial Council Form Field Names

*(To be populated after Phase 5A.5 — downloading and inspecting DISC-001/002/020 PDFs)*

## Appendix B: Pleading Paper Template Specification

*(To be populated after Phase 5A.7 — creating DOCX templates in Word)*

## Appendix C: Full SROG Bank

*(To be populated during Phase 5B.3 — drafting the complete employment SROG bank)*

## Appendix D: Full RFPD Bank

*(To be populated during Phase 5B.4 — drafting the complete employment RFPD bank)*

## Appendix E: Full RFA Bank

*(To be populated during Phase 5B.5 — drafting the complete employment RFA bank)*
