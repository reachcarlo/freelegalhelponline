# Discovery Objection Drafter — Product Requirements Document

**Status**: Draft v3 (revised: input/output flexibility, parser spec, phase adjustment)
**Author**: Product Team
**Date**: 2026-03-04
**Last Updated**: 2026-03-04

---

## 1. Problem Statement

California employment attorneys spend 2–6 hours per case drafting objections to written discovery (interrogatories, requests for production, and requests for admission). This work is highly repetitive: the same objection grounds (relevance, overbreadth, burden, privilege, etc.) recur across virtually every case, animated by the same statutory provisions (CCP §2016.010 et seq.) and case law. Yet attorneys must tailor each objection to the specific request, cite correctly, and maintain uniform formatting across all responses — a tedious, error-prone process that demands legal knowledge but not legal creativity.

**The opportunity**: An objection drafter that combines a static, curated knowledge base of California discovery law with LLM-powered analysis to determine which objections apply and generate request-specific explanations — producing uniform, citation-backed objections that attorneys can copy into their response documents.

---

## 2. Target User

**Primary**: California employment litigation attorneys (plaintiff-side and defense-side) at small-to-mid firms (1–20 attorneys) who handle written discovery responses regularly. These users:

- Prepare 5–15 sets of discovery responses per month
- Want consistent objection formatting across all matters
- Value speed but will not sacrifice accuracy or completeness
- Are already familiar with discovery objection grounds and want *drafting assistance*, not *legal education*
- Currently draft objections manually or from firm-maintained template banks
- May use Word, Google Docs, or PDF-based workflows

**Secondary**: Solo practitioners, law school clinics, and legal aid organizations with limited staffing.

---

## 3. Jobs to Be Done

| Job | Current Solution | Pain Point |
|-----|-----------------|------------|
| "Draft objections that are uniform across all requests in a set" | Copy-paste from prior responses, manually adjust | Inconsistent formatting, missed objections, stale citations |
| "Identify which objections apply to each specific request" | Attorney reads each request, mentally maps to objection grounds | Time-consuming, relies on memory, easy to miss applicable grounds |
| "Ensure every objection has correct statutory and case citations" | Manual lookup or template banks | Templates go stale, citations may be overruled or superseded |
| "Control the verbosity and tone of objections" | Manually rewrite each time | No standardization; varies by attorney, by day, by mood |
| "Process an entire discovery set at once" | Work through requests one-by-one | 35+ requests × manual analysis = hours of repetitive work |
| **"Raise only defensible objections — avoid sanctions for boilerplate"** | Attorney exercises judgment; errs toward over-objecting | CCP §2023.010(e) sanctions for meritless objections; $1,000 mandatory sanctions under §2023.050; *Korea Data Systems* risk |
| **"Prepare meet-and-confer talking points for each objection"** | Attorney reconstructs rationale from memory or notes | CCP §2016.040 (AB 1521) requires good-faith meet-and-confer; long-form explanations serve this dual purpose |

---

## 4. Competitive Analysis Summary

Based on market research (see `learning/market research/discovery/`):

| Competitor | Approach | Strengths | Gaps |
|-----------|----------|-----------|------|
| **Briefpoint** | Upload PDF → parse → bespoke objections + substantive placeholders | Most complete workflow; "Suggest" per request; Bridge for client input | No objection template customization; no verbosity control |
| **Harvey AI** | Workflow Builder → objection table with strength ratings | Flexible; jurisdiction-aware; strength ratings | Requires custom workflow creation; $1K+/mo; no template system |
| **CoCounsel** | Word add-in → draft responses with Practical Law grounding | Structured workflow; Westlaw integration; citation formatting | Tied to Thomson Reuters ecosystem; less objection-specific |
| **AI.Law** | Upload → auto-draft all objections to prevent waiver | Fast (2–7 min); blanket coverage | No selectivity; no template control; over-objects by design |
| **Eve Legal** | Per-request analysis → iterative aggressiveness tuning | Trains on firm tone; plaintiff-focused | $1B+ valuation; enterprise pricing; no format control |
| **NetDocuments ndMAX** | Playbook-driven objection language from firm data tables | Consistent; firm-controlled language | No substantive responses; no LLM analysis |
| **LegalMation** | SMARTOBJECT™ → auto-populate shells with objections | 1.1M+ requests answered; 60-second processing | High-volume defense focus; limited customization |

**Our differentiation** (validated):
1. **Verbosity control** — Short/Medium/Long explanation lengths (genuine gap; no competitor offers this)
2. **Static knowledge base** — Curated CDA statutes + case law, refreshed on schedule (not hallucinated by LLM)
3. **Cost efficiency** — Batch processing (one API call per set); 10–50x cheaper per-use vs. Briefpoint subscription
4. **Employment law specialization** — Tuned for California employment litigation patterns
5. **No ecosystem lock-in** — No Thomson Reuters, no $1K/mo platform; works alongside any DMS
6. **Request-specific explanations** — LLM contextualizes each explanation to the specific request text (not generic boilerplate)
7. **Sanctions awareness** — Tool recommends *fewer, better-justified* objections (opposite of AI.Law's blanket approach)

**Differentiation to validate** (build last):
8. **Template-driven uniformity** — Variable tags for firm style customization (no competitor offers this, but demand is unvalidated)

---

## 5. Feature Specification

### 5.1 Objection Knowledge Base (Static, Local)

The foundation of the tool is a **curated, static knowledge base** of California discovery objection law. This is NOT retrieved dynamically from the LLM — it is structured data that the LLM references during generation.

#### 5.1.1 Objection Taxonomy

Each objection ground is a structured record stored in a **single YAML file** (`config/objections/grounds.yaml`). Citations are embedded inline per ground (not in a separate file) to maintain a single source of truth:

```yaml
objection_id: "relevance"
label: "Relevance"
category: "substantive"  # form | substantive | burden | device_specific
description: "Information not relevant to the subject matter and not reasonably calculated to lead to admissible evidence"
last_verified: "2026-03-01"
statutory_citations:
  - code: "CCP"
    section: "§2017.010"
    reporter_key: null  # statutory citations use code+section as key
    description: "Scope of discovery"
  - code: "CCP"
    section: "§2017.020"
    reporter_key: null
    description: "Court authority to limit discovery"
case_citations:
  - name: "Emerson Electric Co. v. Superior Court"
    year: 1997
    citation: "(1997) 16 Cal.4th 1101, 1108"
    reporter_key: "16 Cal.4th 1101"  # unique identifier for validation
    holding: "Discovery relevance standard is 'extremely broad'"
    use: "Standard definition — use when asserting narrow relevance"
  - name: "Pacific Tel. & Tel. Co. v. Superior Court"
    year: 1970
    citation: "(1970) 2 Cal.3d 161, 173"
    reporter_key: "2 Cal.3d 161"
    holding: "Doubts resolved in favor of permitting discovery"
    use: "Counter-cite — acknowledge broad standard while asserting limit"
applies_to:
  - interrogatories
  - rfps
  - rfas
  - depositions
sample_language:
  short: "not relevant to the subject matter of this action nor reasonably calculated to lead to the discovery of admissible evidence"
  medium: "seeks information not relevant to the subject matter of this action and not reasonably calculated to lead to the discovery of admissible evidence, as the requested information bears no connection to any claim or defense at issue"
  long: "seeks information that is neither relevant to the subject matter involved in this pending action nor reasonably calculated to lead to the discovery of admissible evidence. The requested information has no conceivable connection to any claim, defense, or subject matter at issue in this litigation. California's broad discovery standard notwithstanding, this request exceeds even the liberal scope permitted under CCP §2017.010."
strength_signals:
  - "requests information about unrelated matters"
  - "no connection to claims or defenses"
  - "seeks information about third parties not involved"
```

#### 5.1.2 Complete Objection Ground List

**Form Objections** (8):
1. Vague and Ambiguous
2. Compound, Conjunctive, or Disjunctive
3. Assumes Facts Not in Evidence
4. Calls for Speculation
5. Calls for Legal Conclusion
6. Overbroad as to Time and Scope
7. Argumentative
8. Unintelligible

**Substantive/Privilege Objections** (5):
9. Relevance
10. Attorney-Client Privilege
11. Work Product Doctrine
12. Right to Privacy
13. Trade Secret Privilege

**Burden/Proportionality Objections** (3):
14. Undue Burden and Expense
15. Proportionality
16. Equally Available Information

**Device-Specific Objections** (variable by discovery type):
- Interrogatory: Exceeds 35-limit, compound/conjunctive/disjunctive
- RFP: Failure to particularize, ESI inaccessibility, already produced
- RFA: Exceeds 35-limit, ambiguous/compound
- Deposition: Defective notice, speaking objections, instruct not to answer

Total: **16 universal grounds + device-specific variants**

#### 5.1.3 Knowledge Base Refresh Strategy

- **Static data**: Single YAML file at `config/objections/grounds.yaml` (inline citations per ground)
- **Refresh cadence**: Monthly review (automated detection + manual legal review)
- **Automated detection**: Use existing CourtListener integration (Phase 4B) to flag new decisions citing discovery objection grounds; use existing PUBINFO integration to detect statutory amendments
- **No dynamic retrieval**: LLM does NOT fetch or generate citations — it selects from the knowledge base
- **Versioning**: Each ground includes `last_verified` field; dates older than 6 months trigger a review alert

### 5.2 Objection Template System

Attorneys control the output format via a **template with variable tags**. The template defines the structure of each objection paragraph.

#### 5.2.1 Variable Tags

| Tag | Description | Example Output |
|-----|-------------|----------------|
| `{OBJECTION}` | Objection ground label | "Relevance" |
| `{EXPLANATION}` | Objection explanation text (request-specific) | "seeks information about Plaintiff's medical history, which is not relevant to..." |
| `{STATUTORY_CITATION}` | Primary CCP/Evidence Code citation | "CCP §2017.010" |
| `{CASE_CITATION}` | Leading case citation | "*Emerson Electric Co. v. Superior Court* (1997) 16 Cal.4th 1101" |
| `{ALL_STATUTORY_CITATIONS}` | All applicable statutory cites | "CCP §§2017.010, 2017.020" |
| `{ALL_CASE_CITATIONS}` | All applicable case cites | "*Emerson Electric* (1997) 16 Cal.4th 1101; *Pacific Tel.* (1970) 2 Cal.3d 161" |
| `{REQUEST_NUMBER}` | The request/interrogatory number | "No. 5" |
| `{DISCOVERY_TYPE}` | Type of discovery device | "Interrogatory" |

**Separator** is configured as a separate dropdown ("; " / ". " / newline), not as a template variable — simpler UX.

#### 5.2.2 Default Templates (3 Built-in Presets)

**Default** (most common California practice):
```
Objection: {OBJECTION}: {EXPLANATION} ({STATUTORY_CITATION}; {CASE_CITATION})
```

**Formal/Narrative**:
```
Responding Party objects on the following grounds: Pursuant to {STATUTORY_CITATION}, {OBJECTION}: {EXPLANATION}. {CASE_CITATION}.
```

**Concise**:
```
{OBJECTION} ({STATUTORY_CITATION}).
```

**"Subject to and without waiving" preamble**: Toggle ON/OFF (default OFF). When enabled, prepends: "Subject to and without waiving the foregoing objections, Responding Party responds as follows:..." to the end of the objection block. Tooltip explains: "California courts have criticized boilerplate preambles. See *Korea Data Systems Co. v. Superior Court* (1997) 51 Cal.App.4th 1513."

#### 5.2.3 Template Implementation

- **Engine**: Python `str.format_map()` with a `SafeFormatMap` fallback for missing keys (not Jinja2 — no conditional logic needed, simpler and safer)
- **V1**: Default template + editable text field that resets on page reload. No persistence.
- **V1.5+**: Template persistence via `localStorage`; 3 built-in presets as one-click starting points
- **Frontend**: Pill-based tag insertion (colored, non-editable badges) — not raw curly-brace editing. Attorney types static text normally; clicks tag pills from a palette to insert variables.

### 5.3 Objection Analysis Engine (LLM-Powered)

The LLM performs two tasks: (1) determine which objection grounds apply to each request, and (2) generate request-specific explanation text for each applicable objection.

#### 5.3.1 Three-Stage Pipeline

The analysis is conceptually three stages, even though V1 may fuse stages 1 and 2 into a single LLM call:

```
Stage 1: ANALYSIS — Which objection grounds apply to this request?
   Input: Request text + available grounds
   Output: List of applicable ground_ids + strength rating (HIGH/MEDIUM/LOW)
   ↓
Stage 2: GENERATION — Write the explanation for each applicable objection
   Input: Request text + applicable grounds + verbosity level
   Output: Request-specific explanation text + citation selections
   ↓
Stage 3: FORMATTING — Render through the template engine
   Input: Generated objections + template + separator
   Output: Formatted text ready for copy/paste
```

**Interface contracts** (stable across versions):
```python
class ObjectionAnalyzer:
    """Stage 1+2: Determine applicability and generate explanations."""
    def analyze_batch(self, requests: list[ObjectionRequest], grounds: list[ObjectionGround],
                      verbosity: Verbosity, party_role: PartyRole) -> list[AnalysisResult]: ...
    def analyze_single(self, request: ObjectionRequest, grounds: list[ObjectionGround],
                       verbosity: Verbosity, party_role: PartyRole) -> AnalysisResult: ...

class ObjectionFormatter:
    """Stage 3: Template rendering."""
    def format(self, result: AnalysisResult, template: ObjectionTemplate, separator: str) -> str: ...
    def format_batch(self, results: list[AnalysisResult], template: ObjectionTemplate, separator: str) -> str: ...
```

#### 5.3.2 Batch Processing

All requests in a discovery set are processed in a **single LLM call** using Claude's **tool_use** for guaranteed structured output. If token limits require splitting, the system transparently chunks at 15-request boundaries.

**Structured output via tool_use**:
```python
{
    "name": "submit_objections",
    "description": "Submit the analysis of which objections apply to each discovery request",
    "input_schema": {
        "type": "object",
        "properties": {
            "request_analyses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "request_number": {"type": "integer"},
                        "applicable_objections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "ground_id": {"type": "string", "enum": ["relevance", "overbroad", ...]},
                                    "explanation": {"type": "string"},
                                    "strength": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "statutory_citation_keys": {"type": "array", "items": {"type": "string"}},
                                    "case_citation_keys": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["ground_id", "explanation", "strength"]
                            }
                        },
                        "no_objections_rationale": {"type": "string"}
                    },
                    "required": ["request_number", "applicable_objections"]
                }
            }
        },
        "required": ["request_analyses"]
    }
}
```

**Batch splitting strategy**:
- Estimate input tokens per request (~50 tokens) + system prompt (~4,200 tokens) + estimated output (~200 tokens per request)
- If total exceeds 80% of model context limit, split at 15-request boundaries
- Process chunks sequentially; merge results
- Surface partial results if a chunk fails: "Objections generated for requests 1–15; retrying 16–35..."

**Estimated token budget per batch (35 requests, medium verbosity)**:
- System prompt (16 grounds × ~200 tokens + instructions): ~4,200 tokens
- User input (35 requests × ~50 tokens): ~1,750 tokens
- Output (35 requests × 4 objections × ~50 tokens): ~7,000 tokens
- **Total**: ~13,000 tokens
- **Estimated cost** (Haiku 4.5): ~$0.013 / (Sonnet 4.6): ~$0.10

**Timeout**: 120 seconds for batch processing (35 requests × ~100 tokens/sec output = ~70 seconds typical). Progress indicator shown during generation.

#### 5.3.3 Verbosity Control

Three levels, configured per-session:

| Level | Description | Approximate Length | Use Case |
|-------|-------------|--------------------|----------|
| **Short** | Ground + minimal explanation | 5–15 words | Experienced attorneys who want speed |
| **Medium** | Ground + specific explanation tied to request | 15–30 words | Default; balanced |
| **Long** | Ground + detailed explanation with legal reasoning | 30–60 words | Complex matters; doubles as meet-and-confer preparation |

**Key requirement**: Explanations must reference the specific subject matter of the request. Generic language that could apply to any request is unacceptable. The LLM prompt explicitly instructs: "In each explanation, reference the specific information or subject matter sought by the request. Do not use generic language."

#### 5.3.4 Citation Validation (Post-Processing)

**Strict reporter-key matching** — no fuzzy replacement:

**Pass 1 (Reporter-key match)**: Extract the reporter string (e.g., "16 Cal.4th 1101") from each LLM-output citation via regex. Look up against the `reporter_key` field in the knowledge base. If found → valid.

**Pass 2 (Flag unmatched)**: Any citation whose reporter string does not match a knowledge base entry is flagged as `[unverified]` and shown to the attorney with a warning badge. Do NOT attempt automatic replacement — replacing a hallucinated citation with a real-but-wrong citation is worse than flagging.

**Pass 3 (Ground-scoped validation)**: Verify each citation is attached to the correct objection ground. If the LLM assigns a privacy case to a relevance objection, flag it with: "Citation typically used for [Right to Privacy], not [Relevance]."

**Leverage existing infrastructure**: Use the existing `CaseCitationVerifier` (Phase 4D.1) and `StatuteCitationVerifier` (Phase 4D.2) for cross-validation against CourtListener and the local statutory database.

### 5.4 Objection Selection

The tool defaults to **LLM-recommended objections** — NOT all grounds enabled. This is a critical design decision driven by the sanctions-avoidance JTBD.

**V1 behavior**:
- LLM determines which objections apply to the request
- Results display each applicable objection with a toggle to include/exclude
- Attorney refines post-generation (remove objections that don't fit; the LLM does the initial filtering)
- Requests where no objections apply show: "No objection grounds appear to apply to this request."

**V2+ behavior**:
- Pre-generation ground exclusion available behind "Filter Grounds" collapsible (collapsed by default)
- Auto-filter by discovery type (hide interrogatory-only grounds when processing RFPs)

**Objection ordering**: Default to convention (form objections first → substantive/privilege → burden/proportionality). Future option: sort by strength (high → low).

### 5.5 Request Input & Parsing

The input experience must handle two real-world scenarios seamlessly: (1) attorney copies a wall of text from a document and pastes it, possibly including definitions, instructions, captions, and other non-request content; (2) attorney uploads a Word or PDF discovery shell prepared by their legal assistant. Both scenarios use the **same parser** — the difference is only how text enters the system.

**Critical constraint**: We do NOT support Judicial Council checkbox forms (DISC-001 series) or scanned/image-based PDFs. These require manual entry. The UI must communicate this clearly but non-dismissively.

#### 5.5.1 Unified Input Area

A single input zone accepts both paste and upload — no tabs, no mode switching. The attorney thinks "here are my requests," not "should I paste or upload?"

**Layout**:
- Upper area: Drop zone for .docx/.pdf files (drag-and-drop + "Browse files" link)
- Lower area: Generous textarea (minimum 8 lines, auto-grows to 20 on paste, scrollbar beyond)
- When a file is dropped, the textarea is replaced by a file confirmation card (filename, size, remove button)
- Both always visible in empty state; when one activates, the other shrinks

**Discovery type selector**: Appears after file attachment or after paste exceeds 500 characters. Options: Auto-detect (default), Interrogatories, Requests for Production, Requests for Admission.

**Parse is explicit**: A "Parse Requests" button (not auto-parse on paste) because:
- Attorneys often paste in stages (copy page 1, paste, copy page 2, paste)
- Large pastes take 2–5s to parse; auto-parse creates unresponsive feel
- Attorney may want to clean up pasted text before parsing

**Unsupported format notice**: Always-visible info box below the input area:
> "Supports typed discovery text — interrogatories, RFPs, and RFAs in Word (.docx), PDF, or pasted text. Scanned forms and Judicial Council checkbox forms (DISC-001 series) require manual entry of each request."

#### 5.5.2 Request Parser (Core Engine)

The parser extracts individual requests from unstructured text. It works identically for pasted text and extracted document text.

**Two-pass architecture**:

**Pass 1 — Structural (regex-based, fast)**:
1. Detect document sections: Caption/header, Definitions, Instructions, Preliminary Statement, Requests, Proof of Service
2. Identify discovery type from document title pattern or request header patterns
3. Extract individual requests by numbered header patterns
4. Capture metadata: propounding party, responding party, set number

**Pass 2 — LLM-assisted (slower, for ambiguous input)**:
When Pass 1 finds fewer requests than expected, or when text lacks clear numbered patterns, use LLM to identify request boundaries. This handles poorly formatted documents.

**Request header patterns to match** (from most specific to least):

Interrogatories:
```regex
(?:SPECIAL\s+)?INTERROGATOR(?:Y|IES)\s+(?:NO\.?\s*)?(\d+)\s*[:.\s]
```

Requests for Production:
```regex
(?:REQUEST\s+FOR\s+PRODUCTION\s+(?:OF\s+DOCUMENTS?\s+)?|DEMAND\s+(?:FOR\s+(?:INSPECTION|PRODUCTION)\s+(?:OF\s+DOCUMENTS?\s+)?)?|REQUEST\s+)(?:NO\.?\s*)?(\d+)\s*[:.\s]
```

Requests for Admission:
```regex
(?:REQUEST\s+FOR\s+ADMISSION\s+|ADMISSION\s+)(?:NO\.?\s*)?(\d+)\s*[:.\s]
```

Bare number fallback:
```regex
^\s*(\d+)\s*[.):\s]\s+
```

**Section delimiters** (content before/after these is separated, not treated as requests):
- `DEFINITIONS`, `INSTRUCTIONS`, `PRELIMINARY STATEMENT`, `PROOF OF SERVICE`
- Identification paragraph (`PROPOUNDING PARTY:`, `RESPONDING PARTY:`, `SET NUMBER:`)

**Multi-paragraph handling**: A request's body extends from its header to the next numbered header. This captures "including but not limited to" lists common in RFPs.

**Sub-parts**: Handle `(a)`, `(b)`, `(c)` and `a.`, `b.`, `c.` lettered sub-parts within a request (common in form interrogatories and frequently used — though technically prohibited — in special interrogatories). Sub-parts are kept within the parent request, not split into separate requests.

**Defined terms**: Detect ALL CAPS terms (per CCP §2030.060(e) convention) and, if a Definitions section was parsed, map them back to definitions. Pass defined terms as context to the LLM (affects objection analysis).

**Response shell detection**: When the parser finds interleaved `REQUEST NO. X:` / `RESPONSE TO REQUEST NO. X:` patterns, it recognizes this as a response shell and identifies insertion points for objections.

#### 5.5.3 Parse Preview (Editable Card List)

After parsing, the attorney reviews extracted requests before generation:

**Card list**: Each request displayed as a card with:
- Checkbox (for selective generation; all checked by default)
- Request number and type label
- Request text preview (truncated to ~3 lines; "Show full" expander)
- `[Edit]` button → transforms card into editable textarea
- `[Split]` action → for when the parser merged two requests into one (most common error)
- `[Merge with next]` action → for when the parser split one request into two

**"Skipped sections" panel** (collapsed, below request list):
- Shows what was detected but NOT treated as a request: Definitions, Instructions, Caption, POS
- Each has `[View]` to inspect content and `[Add]` to rescue a misclassified request
- Definitions show count of defined terms

**Bulk controls**: "Select all / Deselect all" at top of request list

**Manual add**: `[+ Add request manually]` at bottom for requests the parser missed entirely

**Sticky footer**: Count of selected requests + "Generate Objections" button

**Failed parse state**: When 0 requests are extracted:
> "No discovery requests found in this file. This can happen when: (1) the file is a scanned image, (2) the file uses Judicial Council checkbox formatting, or (3) the requests use unusual numbering. You can paste the request text directly instead, or add requests manually."

### 5.6 Output Modes

The output must accommodate two orthogonal choices: **content scope** (what is included) and **delivery method** (how it reaches the attorney's document).

#### 5.6.1 Content Scope Toggle

**Segmented control** — two options, instantly switchable (no re-render):

| Mode | Shows | Default When |
|------|-------|-------------|
| **Objections Only** | Just the formatted objection paragraphs, numbered to match requests | Input was pasted text (attorney already has requests in their document) |
| **Request + Objections** | Each request reproduced, followed by formatted objections underneath | Input was uploaded file (attorney works from tool output as reference) |

"Request + Objections" format follows standard California response document convention:
```
REQUEST FOR PRODUCTION NO. 1:
[Request text reproduced]

RESPONSE TO REQUEST FOR PRODUCTION NO. 1:
[Objection text]
```

#### 5.6.2 Delivery Methods

Three buttons, equally weighted:

| Method | Description | Always Available |
|--------|-------------|-----------------|
| **Copy to clipboard** | Plain text (respects current content scope toggle). Primary action — largest button. | Yes |
| **Download .txt** | Plain text file download | Yes |
| **Download .docx** | Formatted Word document (12pt Times New Roman, double-spaced, 1" margins, proper heading styles, italic case names, bold objection grounds) | Yes |

**Fourth option — "Insert into shell"** — appears ONLY when the input was an uploaded .docx file:

> **Insert into your uploaded shell**: Objections will be inserted into `Henderson_v_Acme_RFPs_Set2.docx` after each request, preserving your document's formatting and styles. [18 of 18 insertion points found.] **[Download completed shell (.docx)]**

Shell insertion logic:
1. During parsing, the tool identifies insertion points in the shell (blank lines, `RESPONSE:` placeholders, or consistent structural patterns after each request)
2. Objection text is inserted at each point, inheriting the paragraph style of the adjacent text (preserves fonts, spacing, margins)
3. If not all insertion points are found, warn: "Requests 7 and 14 could not be matched. These objections will be appended at the end."
4. Optional: Insert as tracked changes (toggle) so the attorney can review insertions in Word's Review mode

#### 5.6.3 Per-Request Actions

Each request's result panel includes:
- **Copy** (per-request) — copies just that request's objections
- **Edit objection** — inline editing of the generated text before copy/download
- **Regenerate** — re-runs LLM for just this one request (cheaper than re-running the whole set; useful when attorney edits the request text)

#### 5.6.4 Results Layout

**Desktop** (primary): Two-column layout when "Request + Objections" is selected:
- Left column: Parsed requests (for reference)
- Right column: Generated objections
- **Scroll synchronization**: When attorney scrolls the right column, the left scrolls in tandem so request and objection stay aligned

**Single column** for "Objections Only" mode and for mobile/tablet viewports.

**Sticky summary bar** at bottom: Total objection count across all requests + "Copy All" button + download row

---

## 6. Phased Development Plan

### Phase O.1 — Knowledge Base + Paste-Based Drafter (MVP)

**Goal**: Validate "does the AI select the right objections and produce useful output?" Attorney pastes one or more requests (wall of text) → gets formatted objections.

**Scope**:
- Objection knowledge base: 16 grounds as single structured YAML with inline citations
- **Unified input area**: Textarea for paste (generous, auto-growing) — no upload yet
- **Request parser (structural pass)**: Regex-based extraction of numbered requests from pasted text. Handles definitions/instructions/caption detection and skipping.
- **Parse preview**: Editable card list — attorney reviews, edits, splits, merges, adds, unchecks requests before generation
- **Batch LLM processing**: Single API call via tool_use (or chunked at 15-request boundaries for large sets)
- Discovery type selector (auto-detect + manual override)
- Verbosity selector: Short / Medium / Long (segmented control, default Medium)
- Strength rating: High / Medium / Low per objection
- Citation validation: Strict reporter-key matching; flag unverified
- **Output**: Per-request expandable accordion panels with per-objection toggles
- **Content scope toggle**: "Objections Only" (default) vs. "Request + Objections"
- **Delivery**: Copy to clipboard (primary) + Download .txt
- **Fixed default template** (no template editor)
- "Subject to and without waiving" toggle (default OFF)
- Party role selector (plaintiff/defendant)
- Unsupported format notice (DISC-001 checkbox forms, scanned PDFs)
- Disclaimer on every output

**Why paste + batch is V1 (not single request)**: Attorneys almost never come with a single interrogatory. They have a full set of 5–35 requests. The most common V1 flow is: open Word doc on left monitor → Ctrl+A, Ctrl+C → paste into tool → parse → generate → copy back. Single-request support is a degenerate case of batch (set of 1).

**Backend** (`src/employee_help/discovery/objections/`):
- `knowledge_base.py` — Load/query objection grounds from YAML
- `analyzer.py` — LLM analysis via tool_use (analyze_single + analyze_batch interface)
- `formatter.py` — Template rendering via `str.format_map()`
- `validator.py` — Citation validation (reporter-key matching)
- `parser.py` — Request parser (structural regex pass for V1)
- `models.py` — Data models
- API routes in `api/objection_routes.py`:
  - `POST /api/objections/parse` — Parse pasted text into individual requests
  - `POST /api/objections/generate` — Generate objections for parsed requests

**Frontend** (`frontend/components/discovery/`) — **IMPLEMENTED (2026-03-04)**:
- `objection-drafter.tsx` — Main wizard component (4-step flow: Setup → Input → Review → Results)
- `objection-parse-preview.tsx` — Editable card list for parsed requests
- `objection-results.tsx` — Accordion results with toggles and copy/download
- `frontend/lib/objection-api.ts` — TypeScript API client (types + fetch functions for grounds, parse, generate)
- `frontend/lib/objection-context.tsx` — `ObjectionDrafterContext` (useReducer-based state management)
- Route: `/tools/discovery/objection-drafter` (page.tsx + objection-drafter-page.tsx)
- Added to discovery tools index page with "AI" format badge

**Acceptance Criteria**:
- [x] Attorney can paste a wall of text containing 1–35+ requests → parser extracts individual requests
- [x] Parser correctly skips definitions, instructions, caption, and proof of service
- [x] Parse preview lets attorney edit, split, merge, add, and uncheck requests
- [x] Failed parse (0 requests found) shows helpful diagnostic with manual-add fallback
- [x] LLM generates request-specific objections with strength ratings
- [x] Verbosity control produces visibly different output lengths
- [x] All citations validated against knowledge base; unverified citations flagged
- [x] Requests where no objections apply display "No objections applicable" message
- [x] Content scope toggle switches between "Objections Only" and "Request + Objections"
- [x] Copy-to-clipboard and .txt download work for formatted output
- [ ] Batch (35 requests) completes in < 45 seconds (Haiku) / < 90 seconds (Sonnet) *(backend perf — needs live testing)*
- [ ] Partial failure: show results for successful requests, retry failed *(backend handles chunking; UI surfaces errors)*
- [ ] Cost per batch: < $0.02 (Haiku) / < $0.15 (Sonnet) for 35 requests *(backend cost — needs live testing)*

**Estimated effort**: 2–2.5 weeks

---

### Phase O.2 — Document Upload + Word Export + Shell Insertion

**Goal**: Attorney uploads a discovery shell (.docx or .pdf) → gets objections inserted into their document.

This is the **highest-value workflow**: legal assistants prepare discovery shells (Word docs with each request but empty response sections), and the attorney needs objections inserted. Going from "upload shell → download completed shell" eliminates all copy-paste work.

**Scope**:
- **File upload**: Drag-and-drop zone for .docx and .pdf (unified with paste area)
- **Document text extraction**: python-docx for .docx, pdfplumber for .pdf
- **Enhanced parser**: Same regex engine, plus document structure awareness (paragraph styles, heading detection)
- **Shell detection**: Recognize interleaved `REQUEST NO. X:` / `RESPONSE TO REQUEST NO. X:` patterns
- **Parse preview**: Same editable card list as V1 (with file metadata card: filename, extracted page count)
- **Word export (.docx)**: Generate standalone formatted Word document (12pt Times New Roman, double-spaced, italic case names)
- **Shell insertion**: When input was .docx, offer "Insert into your uploaded shell" — objections inserted at identified insertion points, preserving original formatting
- **Track changes option**: Insert objections as tracked changes for attorney review in Word
- **Fallback**: If document parsing fails, offer "Switch to paste input" with helpful diagnostics

**Backend** (`src/employee_help/discovery/objections/`):
- Enhanced `parser.py` — Document parsing (python-docx text extraction + pdfplumber)
- `exporter.py` — Word document generation + shell insertion (python-docx)
- `POST /api/objections/parse-document` — Upload file → extract requests
- `POST /api/objections/export` — Generate .docx download (standalone or shell-inserted)

**Frontend**:
- Enhanced input area: Drop zone above textarea; file confirmation card with remove button
- "Insert into shell" card in output area (only visible when .docx was uploaded, showing insertion point count)
- Download row: `.txt` / `.docx` / `Insert into shell` buttons

**Acceptance Criteria**:
- [ ] .docx and .pdf upload extracts individual requests correctly
- [ ] Shell documents (with `RESPONSE TO REQUEST NO. X:` patterns) are detected
- [ ] Parse preview works identically to paste flow (edit, split, merge, add)
- [ ] Standalone .docx export has proper legal formatting
- [ ] Shell insertion preserves original document formatting (fonts, spacing, margins)
- [ ] Track changes mode inserts objections as revisions visible in Word's Review tab
- [ ] Insertion point count shown to attorney before download ("18 of 18 insertion points found")
- [ ] Missing insertion points handled gracefully (appended at end with warning)
- [ ] Fallback to paste input on parse failure with helpful messaging
- [ ] 0 requests found: diagnostic message (scanned image? checkbox form? unusual formatting?)

**Estimated effort**: 2.5–3 weeks

---

### Phase O.3 — Template Editor + Presets + Persistence

**Goal**: Validate whether attorneys want to customize objection formatting. Gate: build only if template customization is requested by O.1 users.

**Scope**:
- Template editor: Pill-based tag insertion UI with live preview (side panel on Results step)
- 3 built-in presets (Default, Formal/Narrative, Concise) as one-click starting points
- Separator dropdown ("; " / ". " / newline)
- Template persistence: Save/load custom templates (`localStorage`)
- Pre-generation ground filter: Collapsible checklist (auto-filtered by discovery type), category-grouped pill toggles

**Frontend**:
- `objection-template-editor.tsx` — Pill-based editor with tag palette + live preview
- Template save/load in localStorage
- Ground filter: Reuses ClaimSelector pattern

**Acceptance Criteria**:
- [ ] Pill-based tag insertion works (click tag → inserts at cursor; no raw curly-brace editing)
- [ ] 3 preset templates work as one-click starting points
- [ ] Live preview shows realistic output as attorney edits
- [ ] Templates persist across sessions
- [ ] Ground filter auto-hides device-specific objections not applicable to current discovery type

**Estimated effort**: 1.5 weeks

**Gate**: Ship O.1 first. Get feedback from 5–10 attorneys. Build O.3 only if template customization is demanded.

---

### Phase O.4 — Enhanced Results + Per-Request Controls

**Goal**: Give attorneys granular control over generated objections per-request.

**Scope**:
- **Per-request regenerate**: Re-run LLM for a single request without re-running the whole batch
- **Per-request objection editing**: Inline text editing of generated objection language
- **Desktop two-column layout**: Left column shows parsed requests, right column shows objections, with **synchronized scrolling** so request and objection stay aligned
- **Optional case context**: Free-text field where attorney describes the case (e.g., "wrongful termination / retaliation; plaintiff was senior engineer terminated after reporting safety violations"). Passed to LLM for more relevant objection analysis.
- **Objection style selector**: Standard (all applicable) / Conservative (only strong) / Aggressive (include marginal)
- Smart defaults: Pre-select High/Medium, dim Low-strength objections

**Estimated effort**: 1.5–2 weeks

---

### Phase O.5 — Firm Language Overrides + Learning

**Goal**: Firms can use their own tested objection language; tool learns from attorney choices.

**Scope**:
- Per-ground firm language override: Attorney replaces sample_language with their own tested phrasing
- Override persistence: Server-side per-account (requires auth)
- Learning: Track objection removal rate per ground to improve smart defaults
- Aggregate analytics: Which grounds are most frequently kept/removed?

**Estimated effort**: 2 weeks

---

## 7. Extensibility: Discovery Response Workflow

The objection drafter is one tool in a broader discovery response workflow. The architecture supports future tools that share parsing, state, and knowledge base infrastructure.

### 7.1 Discovery Response Workflow (Future Vision)

```
Discovery Request Document (uploaded or entered)
    ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Parse Requests                                       │
│   Extract individual requests from document                   │
│   [Shared parser — reused by all response tools]              │
├──────────────────────────────────────────────────────────────┤
│ Step 2: Draft Objections (THIS TOOL — Phase O)               │
│   Identify applicable grounds → generate objections           │
│   Template-driven formatting                                  │
├──────────────────────────────────────────────────────────────┤
│ Step 2.5: Client Input Bridge (FUTURE)                       │
│   Translate requests to plain English for client              │
│   Receive structured client answers for substantive responses │
├──────────────────────────────────────────────────────────────┤
│ Step 3: Draft Substantive Responses (FUTURE)                 │
│   RAG-powered responses using case facts + KB                 │
│   "[Subject to and without waiving objections...]"            │
├──────────────────────────────────────────────────────────────┤
│ Step 3.5: Meet-and-Confer Preparation (FUTURE)               │
│   For each objection, generate detailed rationale             │
│   Long-form explanations serve double duty                    │
├──────────────────────────────────────────────────────────────┤
│ Step 4: Generate Privilege Log (FUTURE)                      │
│   Auto-generated for privilege/work product objections (RFPs) │
│   Structured table per CCP §2031.240(c)(1)                   │
│   Data source: objection drafter knows which requests         │
│   triggered privilege objections                              │
├──────────────────────────────────────────────────────────────┤
│ Step 5: Assemble Response Document (FUTURE)                  │
│   Combine objections + responses + verification               │
│   Generate complete response document with caption            │
├──────────────────────────────────────────────────────────────┤
│ Step 6: Prepare Proof of Service (EXISTS)                    │
│   Generate POS for the response set                           │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Shared Components (Build Now, Reuse Later)

| Component | Used by Objection Drafter | Future Reuse |
|-----------|--------------------------|--------------|
| Request Parser | Parse input requests | Substantive responses, privilege log, client bridge |
| Document Upload/Export | Upload requests, export modified doc | Response assembly, document-in/out |
| Discovery Type Selector | Select Interrogatory/RFP/RFA | All discovery response tools |
| Template Engine (`str.format_map`) | Format objection output | Substantive response formatting |
| Knowledge Base (CDA YAML) | Objection grounds + citations | Substantive responses, privilege log requirements |
| Citation Validator | Validate objection citations | Substantive response citations |

### 7.3 Architecture for Extensibility

- **Separate contexts per tool**: `ObjectionDrafterContext` (not extending `DiscoveryContext`) — shared CaseInfo state extracted into a reusable `CaseInfoContext` when multiple tools need it
- **Modular pipeline**: Each step (parse → object → respond → assemble) is an independent module with stable public interfaces
- **Public contracts** (stable APIs):
  - `ObjectionKnowledgeBase.get_grounds(discovery_type)`, `.get_citations(ground_id)`
  - `ObjectionFormatter.format(result, template, separator)`
  - `RequestParser.parse_text(text)`, `.parse_document(file)`
- **Internal implementation** (free to change): LLM prompt format, batch splitting strategy, citation validation regex
- **New enum for response types**: `ResponseDiscoveryType` (INTERROGATORIES, RFPS, RFAS, DEPOSITIONS) — separate from existing `DiscoveryToolType` which describes request generation tools

---

## 8. Technical Architecture

### 8.1 Backend

**Module location**: `src/employee_help/discovery/objections/` (under `discovery/`, not `tools/` — the objection drafter requires LLM calls and knowledge base lookups, unlike the pure-computation tools in `tools/`).

```
src/employee_help/
├── discovery/
│   ├── objections/
│   │   ├── __init__.py
│   │   ├── knowledge_base.py    # Load + query objection grounds from YAML
│   │   ├── analyzer.py          # LLM analysis orchestration (tool_use)
│   │   ├── formatter.py         # Variable tag rendering (str.format_map)
│   │   ├── validator.py         # Citation validation (reporter-key matching)
│   │   ├── parser.py            # Document parsing (V3+, python-docx + pdfplumber)
│   │   └── models.py            # ObjectionGround, GeneratedObjection, etc.
│   ├── models.py                # Existing discovery models (shared)
│   ├── srogs.py, rfpds.py, ...  # Existing request banks
│   └── generator/               # Existing document generation
├── api/
│   └── objection_routes.py      # API endpoints
config/
├── objections/
│   └── grounds.yaml             # Single file: 16+ grounds with inline citations
├── prompts/
│   └── objection_system.j2      # LLM system prompt
```

### 8.2 API Endpoints

| Method | Endpoint | Phase | Purpose | Rate Limit |
|--------|----------|-------|---------|------------|
| GET | `/api/objections/grounds` | O.1 | List all objection grounds (for UI checklist) | 20/min |
| POST | `/api/objections/parse` | O.1 | Parse pasted text into individual requests | 10/min |
| POST | `/api/objections/generate` | O.1 | Generate objections for parsed request(s) | 5/min |
| POST | `/api/objections/parse-document` | O.2 | Upload .docx/.pdf → extract requests | 10/min |
| POST | `/api/objections/export` | O.2 | Generate .docx (standalone or shell-inserted) | 10/min |

### 8.3 Data Models

```python
@dataclass(frozen=True)
class StatutoryCitation:
    code: str          # "CCP", "Evid. Code"
    section: str       # "§2017.010"
    description: str

@dataclass(frozen=True)
class CaseCitation:
    name: str          # "Emerson Electric Co. v. Superior Court"
    year: int          # 1997
    citation: str      # "(1997) 16 Cal.4th 1101, 1108"
    reporter_key: str  # "16 Cal.4th 1101" — unique ID for validation
    holding: str
    use: str           # When to cite this case

class ObjectionCategory(str, Enum):
    FORM = "form"
    SUBSTANTIVE = "substantive"
    BURDEN = "burden"
    DEVICE_SPECIFIC = "device_specific"

class Verbosity(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class ObjectionStrength(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ResponseDiscoveryType(str, Enum):
    INTERROGATORIES = "interrogatories"
    RFPS = "rfps"
    RFAS = "rfas"

@dataclass(frozen=True)
class ObjectionGround:
    ground_id: str
    label: str
    category: ObjectionCategory
    description: str
    last_verified: str
    statutory_citations: tuple[StatutoryCitation, ...]
    case_citations: tuple[CaseCitation, ...]
    applies_to: tuple[ResponseDiscoveryType, ...]
    sample_language: dict[Verbosity, str]
    strength_signals: tuple[str, ...]

@dataclass(frozen=True)
class ObjectionRequest:
    request_number: int | str
    request_text: str
    discovery_type: ResponseDiscoveryType

@dataclass
class GeneratedObjection:
    ground: ObjectionGround
    explanation: str                          # LLM-generated, request-specific
    verbosity: Verbosity
    strength: ObjectionStrength
    statutory_citations: list[StatutoryCitation]
    case_citations: list[CaseCitation]
    citation_warnings: list[str]             # Any validation warnings

@dataclass
class AnalysisResult:
    request: ObjectionRequest
    objections: list[GeneratedObjection]
    no_objections_rationale: str | None      # Explains when no objections apply
    formatted_output: str                    # Template-rendered text

class PartyRole(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
```

### 8.4 LLM Integration

**Model selection**:
- Default: Claude Haiku 4.5 (cost-efficient for batch processing)
- Premium option: Claude Sonnet 4.6 (higher quality for complex analysis)

**Structured output**: Via Claude's `tool_use` (guaranteed valid JSON, no parsing failures). Requires adding `generate_with_tools()` method to existing `LLMClient`.

**Prompt requirements**:
- Include full objection knowledge base (grounds + citations) in system prompt
- Instruct LLM to reference specific request text in every explanation
- Instruct LLM to output strength ratings (HIGH/MEDIUM/LOW) per objection
- Instruct LLM to use ONLY citation keys from the knowledge base
- Instruct LLM to include `no_objections_rationale` when a request needs zero objections
- Restrict output to selected/available grounds only

### 8.5 Frontend Architecture

**4-step wizard flow**:

```
Step 1: Setup
  - Discovery type selector (Auto-detect / Interrogatory / RFP / RFA)
  - Verbosity selector (Short / Medium / Long — segmented control with word-count labels + live sample)
  - Party role selector (Plaintiff / Defendant)
  - "Subject to and without waiving" toggle (default OFF)

Step 2: Input (Unified)
  - Upper zone: Drop area for .docx/.pdf files (drag-and-drop + "Browse files" link)
  - Lower zone: Generous textarea (min 8 lines, auto-grows to 20)
  - "Parse Requests" button (explicit, not auto-parse)
  - Unsupported format notice (always visible, info style)
  - On parse: 3-step progress indicator (detect type → extract requests → identify metadata)

Step 3: Review Parsed Requests
  - Editable card list (checkbox + number + truncated text + Edit/Split/Merge actions)
  - "Skipped sections" panel (collapsed) showing Definitions, Instructions, etc.
  - Extracted metadata card (case name, set number, propounding party — editable)
  - "Select all / Deselect all" bulk controls
  - "+ Add request manually" at bottom
  - Sticky footer: "{N} requests selected" + "Generate Objections" button

Step 4: Results
  - Content scope toggle: "Objections Only" / "Request + Objections" (segmented control)
  - Per-request expandable accordion panels (first expanded, rest collapsed)
    - Header: request number + truncated preview + objection count + strength summary
    - Body: per-objection cards with strength badge + toggle + explanation + citation badges
    - Per-request actions: Copy / Edit objection / Regenerate (O.4+)
  - "No objections applicable" message when appropriate
  - Sticky summary bar: total objection count + "Copy All" button
  - Download row: .txt / .docx / "Insert into shell" (when .docx was uploaded, O.2+)
  - "Customize Template" button → opens side panel (O.3+)
  - Desktop (O.4+): Two-column layout with synchronized scrolling
```

**Reuse existing components**:
- `WizardStepper` + `WizardNavigation` from `discovery/`
- `ClaimSelector` pattern for objection ground filter (O.3+)
- Citation badge pattern from `citation-badges.tsx`
- Error banner pattern from `docx-wizard.tsx`
- Download button pattern from `discovery/download-button.tsx`

**State management**: New `ObjectionDrafterContext` at `frontend/lib/objection-context.tsx` (separate from `DiscoveryContext`). Key state:
- `inputMode: 'paste' | 'upload'`
- `uploadedFile: File | null` — preserved for shell insertion
- `parsedRequests: ParsedRequest[]` — editable request cards
- `skippedSections: SkippedSection[]` — definitions, instructions, etc.
- `extractedMetadata: CaseMetadata` — case name, parties, set number
- `selectedRequestIds: Set<string>` — which requests to generate for
- `verbosity: Verbosity`
- `partyRole: PartyRole`
- `discoveryType: ResponseDiscoveryType`
- `results: AnalysisResult[]` — generated objections
- `contentScope: 'objections_only' | 'request_and_objections'`
- `includeWaiverLanguage: boolean`

---

## 9. Knowledge Base Content Specification

### 9.1 Statutory Sources (Already in KB)

The existing Employee Help knowledge base already contains all relevant statutory codes:
- **CCP (Code of Civil Procedure)**: Full text including Civil Discovery Act (§2016.010 et seq.)
- **Evidence Code**: Privilege provisions (§§950–962, 1060–1063)
- **California Constitution**: Art. I, §1 (privacy)

The objection tool's static knowledge base **cross-references** these existing sources but maintains its own curated subset for prompt injection (keeping the LLM prompt focused and cost-efficient). The two are not coupled.

### 9.2 Case Law Citations

The knowledge base includes the **essential canon** of discovery objection case law (~20 cases):

**Foundational**:
- *Greyhound Corp. v. Superior Court* (1961) 56 Cal.2d 355
- *Coy v. Superior Court* (1962) 58 Cal.2d 210
- *Deyo v. Kilbourne* (1978) 84 Cal.App.3d 771

**Privilege/Privacy**:
- *Williams v. Superior Court* (2017) 3 Cal.5th 531
- *Costco Wholesale Corp. v. Superior Court* (2009) 47 Cal.4th 725
- *Coito v. Superior Court* (2012) 54 Cal.4th 480
- *Hill v. National Collegiate Athletic Assn.* (1994) 7 Cal.4th 1

**Burden/Scope**:
- *Calcor Space Facility, Inc. v. Superior Court* (1997) 53 Cal.App.4th 216
- *Emerson Electric Co. v. Superior Court* (1997) 16 Cal.4th 1101
- *West Pico Furniture Co. v. Superior Court* (1961) 56 Cal.2d 407

**Boilerplate/Sanctions**:
- *Korea Data Systems Co. v. Superior Court* (1997) 51 Cal.App.4th 1513
- *Clement v. Alegre* (2009) 177 Cal.App.4th 1277

**Procedural**:
- *Golf & Tennis Pro Shop, Inc. v. Superior Court* (2022) 84 Cal.App.5th 127
- *Vidal Sassoon, Inc. v. Superior Court* (1983) 147 Cal.App.3d 681

### 9.3 Refresh Protocol

| Data Type | Refresh Cadence | Method | Owner |
|-----------|----------------|--------|-------|
| Statutory citations | Monthly | Automated: cross-check against PUBINFO database | Auto + review |
| Case law citations | Monthly | Automated: flag via CourtListener (existing Phase 4B integration) | Auto + review |
| New legislation | January each year | Monitor California legislative session | Manual |
| Objection ground definitions | As needed | Legal review triggered by stale `last_verified` (>6 months) | Manual |

---

## 10. Success Metrics

### 10.1 Core Product Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to generate (single request) | < 5 seconds | API response time |
| Time to generate (35-request batch) | < 45 seconds | API response time |
| Citation accuracy | 100% validated | All citations match knowledge base reporter_key |
| **Objection applicability accuracy** | > 85% | Attorney keeps ≥ 85% of suggested objections |
| **Objection removal rate** | < 30% | % of suggested objections attorney removes |
| **Copy-to-clipboard rate** | > 70% | % of generated results that get copied (strongest utility signal) |
| **Time-to-first-value** | < 60 seconds | Page load → first generated objection |
| "No objections" rate | > 0% | Tool correctly identifies requests needing zero objections |

### 10.2 Cost Metrics

| Scenario | Model | Estimated Cost |
|----------|-------|----------------|
| Single request, Haiku | claude-haiku-4-5 | < $0.005 |
| 35-request batch, Haiku | claude-haiku-4-5 | < $0.02 |
| Single request, Sonnet | claude-sonnet-4-6 | < $0.05 |
| 35-request batch, Sonnet | claude-sonnet-4-6 | < $0.15 |

### 10.3 Business Metrics (Post-Launch)

| Metric | Target | Notes |
|--------|--------|-------|
| Repeat usage (30 days) | > 60% | Attorney returns for another discovery set |
| Template customization rate | Track only | Do not target — validate demand first |
| Conversion (free trial → paid) | > 10% | Assuming 3 free single-request generations |

---

## 11. Pricing Model

This is a **premium attorney feature** (not a free consumer tool).

| Tier | Price | Includes | Rationale |
|------|-------|----------|-----------|
| **Free trial** | $0 | 3 single-request generations (Haiku only) | Enough to evaluate quality, not enough for real work |
| **Professional** | $49/month | Unlimited Haiku generations, batch processing, template customization | Below Briefpoint ($129–249), competitive with attorney subscription |
| **Pro+** | $99/month | Professional + Sonnet model + document upload (O.3+) | Higher quality model for complex matters |

Aligns with broader product pricing ($49–99/month attorney subscription from EXPANDED_REQUIREMENTS.md).

---

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM hallucinating citations | Attorney sanctions for bad cite | Strict reporter-key validation; flag unverified; leverage existing CaseCitationVerifier |
| Over-objecting | Attorney sanctions for boilerplate | Default to LLM-recommended (not all enabled); strength ratings; sanctions disclaimer |
| Knowledge base goes stale | Incorrect citations | Monthly automated detection via CourtListener + PUBINFO; `last_verified` visible to user |
| Template system too complex | Low adoption | Defer template editor to O.1b; validate demand first; pill-based UI (not curly-brace) |
| Token limits exceeded | API call fails or truncates | Batch splitting at 15-request boundaries; partial result surfacing; 120s timeout |
| Quality degradation late in batch | 35th request gets worse analysis | Monitor accuracy by position; split into multiple calls if degradation detected |
| Document parsing fails | Attorney cannot use upload | Graceful fallback to batch text input; clear error messaging |

---

## 13. Legal & Ethical Considerations

- **Disclaimer**: Every output includes: "This tool provides draft objections for attorney review. All objections must be reviewed by a licensed attorney before service. Meritless objections may result in sanctions under CCP §2023.010(e) and §2023.050."
- **No unauthorized practice of law**: Tool is designed for use BY attorneys, not as a substitute for legal judgment
- **No data retention of request content**: Request text processed but not stored (privacy-first)
- **Attorney remains the decision-maker**: Tool suggests objections; attorney decides which to raise
- **Sanctions awareness**: Tool recommends fewer, better-justified objections — explicit anti-boilerplate stance

---

## 14. Resolved Questions

| # | Question | Resolution | Rationale |
|---|----------|-----------|-----------|
| 1 | Plaintiff-side vs. defense-side? | **Both equally.** Add `party_role` field to track usage patterns; specialize defaults in O.4 based on data. | Objection law is procedurally identical regardless of side. |
| 2 | Federal discovery (FRCP)? | **No. Not in Phase O. California-only.** | Federal expansion dilutes California specialization and puts us against Harvey/CoCounsel. Track demand; separate product decision if validated. |
| 3 | "Subject to and without waiving"? | **Template toggle, default OFF.** Tooltip cites *Korea Data Systems*. | Easy win; respects attorney preference while educating on risks. |
| 4 | Request-specific explanations? | **Yes. V1 requirement.** LLM must reference the specific request text. | Generic boilerplate is sanctionable under *Korea Data Systems*. This is our core differentiator vs. static template banks. |
| 5 | Priority ordering? | **Convention by default** (form → substantive → burden). Future option for strength-based ordering. | Matches majority California practice. |

---

## 15. Testing Strategy

### Unit Tests (~60 tests)

**Knowledge base** (8–10 tests): Valid YAML loading, required field validation, discovery type filtering, ground enumeration, `last_verified` staleness detection.

**Request parser** (15–18 tests): This is the highest-risk component — test thoroughly.
- SROG header variants (ALL CAPS, mixed case, with/without colon, abbreviated)
- RFP header variants (REQUEST FOR PRODUCTION, DEMAND FOR INSPECTION, bare number)
- RFA header variants (REQUEST FOR ADMISSION, ADMISSION, bare number with "Admit that")
- Multi-paragraph request body (extends to next numbered header)
- Sub-parts `(a)`, `(b)`, `(c)` kept within parent request
- Definitions section correctly skipped (not treated as requests)
- Instructions section correctly skipped
- Caption/header/POS correctly skipped
- Defined terms (ALL CAPS) detected and mapped to definitions
- Response shell pattern detection (`RESPONSE TO REQUEST NO. X:`)
- Identification paragraph extraction (propounding party, responding party, set number)
- Discovery type auto-detection from document title and header patterns
- Edge case: bare numbered list with no header labels
- Edge case: 0 requests found (returns empty list, not error)
- Edge case: single request (degenerate batch of 1)

**Template engine** (8–10 tests): Default template rendering, all variable substitution, missing variables handled gracefully, separator application, empty objection list, literal brace handling.

**Citation validator** (10–12 tests): Exact reporter-key match, year transposition still matches on reporter, partial case name matches on reporter, fabricated citation flagged, cross-ground citation flagged, statutory citation normalization.

**Models** (5–8 tests): Serialization/deserialization, Pydantic validation, enum coverage.

**Batch splitting** (5 tests): Small batch (1 call), large batch (2+ calls), token estimation, merge logic, partial failure handling.

### Integration Tests (~20 tests, mocked LLM via respx)

**Analyzer** (10 tests): Single request, batch request, verbosity effect, ground exclusion, tool_use parsing, malformed output handling, timeout retry, "no objections applicable" case.

**Parser + Analyzer pipeline** (5 tests): Paste raw text → parse → generate objections end-to-end. Includes messy input with definitions/instructions mixed in.

**API endpoints** (5 tests): `/parse` with valid text, `/parse` with 0 requests (diagnostic response), `/generate` with valid requests, rate limiting, `/parse-document` with .docx upload (O.2).

### E2E Tests (~5 tests, @pytest.mark.llm)

Full pipeline with live LLM: batch of 10 SROGs pasted, batch of 10 RFPs pasted, verbosity comparison, citation validation, cost under target.

### Test Fixtures

- `tests/fixtures/objection_grounds_test.yaml` — Minimal 3-ground knowledge base for fast tests
- `tests/fixtures/llm_objection_responses/` — Canned tool_use responses
- `tests/fixtures/discovery_shells/` — Sample discovery shell documents (.docx) for parser tests:
  - `srog_set_one.txt` — Clean special interrogatories with definitions + instructions
  - `rfp_set_two.txt` — Requests for production with "including but not limited to" lists
  - `rfa_set_one.txt` — Requests for admission with "Admit that" prefix pattern
  - `messy_input.txt` — Mixed formatting, inconsistent numbering, extra whitespace
  - `response_shell.txt` — Interleaved request/response pattern (for shell detection)

---

## Appendix A: Mapping to Existing Codebase

| New Component | Existing Pattern | Notes |
|---------------|-----------------|-------|
| `discovery/objections/` | `discovery/srogs.py`, `discovery/rfpds.py` | Same package; analogous to request banks |
| `discovery/objections/parser.py` | No direct analog | New; regex-based request extraction. Reusable by future discovery response tools. |
| `discovery/objections/exporter.py` | `discovery/generator/docx_builder.py` | Same python-docx pattern for Word generation |
| `config/objections/grounds.yaml` | `config/sources/*.yaml` | Same YAML config pattern |
| `api/objection_routes.py` | `api/discovery_routes.py` | Same route module pattern |
| `objection-drafter.tsx` | `discovery/docx-wizard.tsx` | Same wizard pattern (4 steps) |
| `objection-parse-preview.tsx` | `discovery/request-builder.tsx` | Similar card-list with checkboxes + inline edit |
| `ObjectionDrafterContext` | `DiscoveryContext` | Separate context; shared CaseInfo later |
| LLM tool_use integration | `generation/llm.py` | Add `generate_with_tools()` method |
| Citation validation | `generation/citation_verifier.py` | Reuse existing verifier infrastructure |
| File upload UI | `discovery/download-button.tsx` (inverse) | New drop zone component; reusable for future upload features |

## Appendix B: Request Parser Patterns Reference

**Comprehensive regex patterns for the structural parser** (see `learning/market research/discovery/` formatting research):

**Interrogatory headers** (10+ variations):
- `SPECIAL INTERROGATORY NO. 1:` / `INTERROGATORY NO. 1:` / `INTERROGATORY NO. 1.`
- Mixed case: `Special Interrogatory No. 1:` / Abbreviated: `SROG NO. 1:`
- Bare number: `1.  State all facts...` / `1)  State all facts...`

**RFP headers** (12+ variations):
- `REQUEST FOR PRODUCTION OF DOCUMENTS NO. 1:` / `REQUEST FOR PRODUCTION NO. 1:`
- `DEMAND FOR PRODUCTION OF DOCUMENTS NO. 1:` / `DEMAND FOR INSPECTION NO. 1:`
- `DEMAND NO. 1:` / `REQUEST NO. 1:` / `RFP NO. 1:`

**RFA headers** (6+ variations):
- `REQUEST FOR ADMISSION NO. 1:` / `ADMISSION NO. 1:` / `RFA NO. 1:`
- Bare: `1.  Admit that...`

**Section delimiters** (skip these, do not treat as requests):
- `DEFINITIONS` / `INSTRUCTIONS` / `PRELIMINARY STATEMENT` / `PROOF OF SERVICE`
- `PROPOUNDING PARTY:` / `RESPONDING PARTY:` / `SET NUMBER:`

**Response shell patterns** (detect for insertion point identification):
- `RESPONSE TO SPECIAL INTERROGATORY NO. 1:` / `RESPONSE TO REQUEST NO. 1:`

**Sub-parts** (keep within parent request, do not split):
- `(a)`, `(b)`, `(c)` / `a.`, `b.`, `c.` / `(i)`, `(ii)`, `(iii)`

**Multi-paragraph handling**: Request body extends from its header to the next numbered header. "Including but not limited to" lists (common in RFPs) stay with their parent request.

**Defined terms**: ALL CAPS words per CCP §2030.060(e) convention. Map back to Definitions section if parsed. Pass to LLM as context.

## Appendix C: Example End-to-End Flow (V1 — Paste)

```
1. Attorney navigates to /tools/discovery/objection-drafter

2. Step 1 (Setup):
   - Discovery Type = "Auto-detect"
   - Verbosity = "Medium"
   - Party Role = "Defendant"
   - "Subject to and without waiving" = OFF

3. Step 2 (Input):
   Attorney opens discovery shell in Word on left monitor, selects all
   (Ctrl+A), copies (Ctrl+C), pastes (Ctrl+V) into the textarea.

   The pasted text includes:
   - Caption ("SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES...")
   - Identification paragraph ("PROPOUNDING PARTY: Plaintiff Jane Henderson...")
   - Definitions section (12 defined terms: DOCUMENT, YOU, PERSON, etc.)
   - Instructions section (8 paragraphs)
   - 22 Requests for Production
   - Proof of Service

   Attorney clicks "Parse Requests".

4. Progress indicator:
   ✓ Detected request type: Requests for Production
   ▸ Extracting individual requests... (2 seconds)
   ✓ Identified 22 requests, 12 definitions, 3 skipped sections

5. Step 3 (Review Parsed Requests):
   ┌ Extracted metadata ──────────────────────────────────┐
   │  Case: Henderson v. Acme Corp, No. 24-CV-1234       │
   │  Set:  Two    Propounding: Plaintiff                 │
   └──────────────────────────────────────────────────────┘

   ☑ REQUEST NO. 1: All DOCUMENTS relating to any COMMUNICATION
     between YOU and PLAINTIFF regarding the terms of... [Show full]
   ☑ REQUEST NO. 2: All DOCUMENTS relating to any employment
     policies, procedures, or handbooks applicable to... [Show full]
   ... (20 more requests)

   Skipped: Caption, Definitions (12 terms), Instructions (8 para), POS

   Attorney scans the list — all 22 look correct.
   Clicks "Generate Objections" (LLM call, ~12 seconds for 22 requests)

6. Step 4 (Results):
   Toggle: [Objections Only] / Request + Objections

   ▼ REQUEST FOR PRODUCTION NO. 1                    3 objections
     ☑ [HIGH] Overbroad — This request seeks "all documents" relating
       to any communication regarding employment terms without reasonable
       limitation as to time period, author, or subject matter.
       (CCP §§2017.010, 2017.020; Calcor Space Facility, Inc. v.
       Superior Court (1997) 53 Cal.App.4th 216)
     ☑ [MEDIUM] Vague and Ambiguous — The phrase "relating to" is
       undefined and susceptible to multiple reasonable interpretations
       as applied to communications about "terms of employment."
       (CCP §2031.060; Deyo v. Kilbourne (1978) 84 Cal.App.3d 771)
     ☐ [LOW] Right to Privacy — To the extent this request seeks
       personal communications between Responding Party and third-party
       employees, such communications implicate privacy interests.
       (Cal. Const. Art. I, §1; Williams v. Superior Court (2017)
       3 Cal.5th 531)
     [Copy]

   ▸ REQUEST FOR PRODUCTION NO. 2                    2 objections
   ▸ REQUEST FOR PRODUCTION NO. 3                    4 objections
   ▸ REQUEST FOR PRODUCTION NO. 4                    0 objections
     "No objection grounds appear to apply to this request."
   ... (18 more)

   ──────────────────────────────────────
   46 total objections across 22 requests
   [Copy All]    [Download .txt]    [Download .docx]

7. Attorney reviews: toggles OFF the LOW-strength privacy objection on
   Request 1. Checks that Request 4 correctly has no objections (it's a
   straightforward document request). Edits the overbroad explanation on
   Request 7 to mention a specific time period.

8. Clicks "Copy All" → pastes into Word response document.
   Total time: ~3 minutes for 22 requests.
```

## Appendix D: Example End-to-End Flow (V2 — Upload Shell)

```
1. Attorney navigates to /tools/discovery/objection-drafter

2. Step 1 (Setup): Same as above.

3. Step 2 (Input):
   Attorney drags "Henderson_v_Acme_RFPs_Set2.docx" from desktop onto
   the drop zone.

   File card appears:
   [Word icon]  Henderson_v_Acme_RFPs_Set2.docx  42 KB  [x]
   Discovery type: Auto-detect (•)

   Clicks "Parse Requests".

4-6. Same as paste flow (parse preview → generate → results).

7. Output area now shows an additional option:

   ┌─────────────────────────────────────────────────────┐
   │  ★ Insert into your uploaded shell                  │
   │                                                     │
   │  Objections will be inserted into                   │
   │  Henderson_v_Acme_RFPs_Set2.docx after each         │
   │  request, preserving your document's formatting.    │
   │                                                     │
   │  22 of 22 insertion points found.                   │
   │  ☐ Insert as tracked changes                        │
   │                                                     │
   │  [Download completed shell (.docx)]                 │
   └─────────────────────────────────────────────────────┘

8. Attorney clicks "Download completed shell (.docx)".
   Opens the file in Word — all 22 responses have objections inserted
   at the correct location, in the document's original formatting.
   Attorney reviews in Word, adds substantive responses below the
   objections, and serves.
   Total time: ~3 minutes (vs. 2–4 hours manually).
```
