# Privacy & Data Protection Implementation Plan

**Date**: 2026-03-15
**Scope**: LITIGAGENT case tools (case chat, objection drafter, discovery tools within the case workspace)
**Status**: All phases COMPLETE — P2 (2026-03-15), P1 (2026-03-15), P3 (2026-03-15)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Data Flow Audit](#2-data-flow-audit)
3. [Scope of Protection](#3-scope-of-protection)
4. [Phase P2: Obfuscation Engine](#4-phase-p2-obfuscation-engine)
5. [Phase P1: Informed Consent & Terms](#5-phase-p1-informed-consent--terms)
6. [Phase P3: Encryption at Rest](#6-phase-p3-encryption-at-rest)
7. [Implementation Schedule](#7-implementation-schedule)
8. [Appendix A: File-by-File Audit](#appendix-a-file-by-file-audit)
9. [Appendix B: Legal Framework & Liability](#appendix-b-legal-framework--liability)
   - [B.1 The Rule: ABA Formal Opinion 477R](#b1-the-rule-aba-formal-opinion-477r)
   - [B.2 Our Reasonable Efforts: What We Do](#b2-our-reasonable-efforts-what-we-do)
   - [B.3 What We Cannot Guarantee: Honest Limitations](#b3-what-we-cannot-guarantee-honest-limitations)
   - [B.4 Contractual Terms: Allocation of Risk](#b4-contractual-terms-allocation-of-risk)
   - [B.5 How This Should Be Communicated to Users](#b5-how-this-should-be-communicated-to-users)
   - [B.6 Disclosure Surface Inventory](#b6-disclosure-surface-inventory)

---

## 1. Executive Summary

### The single privacy gap

The Anthropic Claude API is the **only path** where user data leaves our server. Every other component — file extraction, OCR, embeddings, vector search, database — runs entirely locally with zero network calls.

### What we're protecting

LITIGAGENT case tools — where attorneys upload case files, draft discovery, and analyze case strategy. This is where privileged material and work product flow. The homepage chat (consumer + attorney mode) is general legal research; attorneys asking "What does Cal. Lab. Code § 1102.5 say?" are not putting case-identifying information at risk. We address the homepage with informed consent only.

### Architecture decision: Obfuscate at the API boundary, not in storage

Our data stays clean. We store real party names, real filenames, real case content in our database. Obfuscation runs **only** at the moment we send data to Anthropic, and deobfuscation runs when we receive the response. The entity map is ephemeral — it lives for the duration of one API call and is never persisted. This means:

- No parallel storage of obfuscated/real values
- No stale mapping tables to maintain
- Case metadata can change freely without syncing obfuscation state
- Data integrity is never compromised by obfuscation logic

### Priority order

| Phase | What | Why First | Effort |
|---|---|---|---|
| **P2** | Obfuscation engine | The engineering substance — prevents identifying data from reaching Anthropic | 4-5 days |
| **P1** | Informed consent + terms | The legal protection — disclosed, documented, defensible | 2-3 days |
| **P3** | Encryption at rest | Defense in depth — protects data on our server | 2-3 days |

P4 (audit trail), P5 (auto-expiry), P6 (self-hosted LLM) are deferred. They add cost and complexity that isn't justified at this stage.

---

## 2. Data Flow Audit

### What leaves the server

| Destination | Data Sent | Trigger | Obfuscation Scope |
|---|---|---|---|
| **Anthropic Claude API** | Query text, case file chunks, attorney notes, conversation history, discovery request text | LLM generation calls from LITIGAGENT tools | **P2 covers this** |
| **Anthropic Claude API** | Query text, KB chunks (public law) | Homepage chat (`/api/ask`) | **P1 disclosure only** |
| **Sentry** (optional) | Error stack traces | Unhandled errors | Disabled by default |
| **Plausible** (optional) | Anonymous page views | Navigation | No PII, no action needed |
| **Google/Microsoft OAuth** | Standard auth (email, name) | User login | No case data, no action needed |

### What stays local

Every component that handles case files runs locally:

| Component | Library | Network Calls |
|---|---|---|
| PDF extraction | pdfplumber | None |
| DOCX extraction | python-docx | None |
| Excel extraction | openpyxl | None |
| CSV extraction | stdlib csv | None |
| Email extraction | stdlib email, extract-msg | None |
| Image OCR | pytesseract + Pillow | None |
| Embeddings | sentence-transformers (BGE) | None (model pre-cached) |
| Vector search | LanceDB | None (embedded DB) |
| Database | SQLite (WAL) | None |
| Doc generation | PyPDFForm, docxtpl | None |

### Anthropic's data policy

- API inputs are **not used for training**
- **30-day retention** for trust & safety monitoring, then deleted
- SOC 2 Type II certified
- Zero Data Retention (ZDR) available for enterprise agreements

---

## 3. Scope of Protection

### What we obfuscate (P2)

LITIGAGENT case workspace tools — any API call that includes case-specific content:

| Path | Data at Risk | Obfuscation Applied |
|---|---|---|
| Case chat (`/api/cases/{id}/chat`) | Case file chunks, attorney notes, query, filenames, conversation history | **Yes** |
| Objection drafter (`/api/objections/generate`) when called from case workspace | Discovery request text | **Yes** |
| Tier 2 metadata extraction (LITIGAGENTv2) | Case file content sent for LLM-assisted extraction | **Yes** |
| Discovery generation (`/api/discovery/generate`) | None — local PDF/DOCX generation, no LLM call | N/A |
| Calculators, intake, agency routing | None — rule-based, no LLM call | N/A |

### What we do NOT obfuscate (P1 disclosure only)

Homepage chat (`/api/ask`) in consumer or attorney mode. Attorneys using the general chat for legal research ("What are the elements of a FEHA retaliation claim?") are not inputting case-identifying data. We disclose the data flow and let them decide.

### What we never transmit

- SSN, EIN → hard-redacted (replaced with `[REDACTED]`, irreversible)
- Raw uploaded files → never sent to Anthropic; only retrieved chunks from local vector search
- User credentials, tokens → never included in LLM calls

---

## 4. Phase P2: Obfuscation Engine

### 4.1 Core Design

The obfuscation engine is a **stateless, ephemeral service** that runs at the Anthropic API call boundary. It does three things:

1. **Scan** text for identifying entities (names, companies, emails, phones, case numbers)
2. **Replace** each entity with a deterministic placeholder (`PERSON_1`, `COMPANY_1`, etc.)
3. **Reverse** the replacement on the response text

The entity map lives only in memory for the duration of one request-response cycle. It is never stored in the database, never logged, and never persisted.

```
┌─────────────────────── Our Server ──────────────────────────┐
│                                                              │
│  SQLite (real data)     Retrieval (real queries)             │
│         │                       │                            │
│         ▼                       ▼                            │
│  ┌──────────────────────────────────────┐                    │
│  │         ObfuscationContext           │                    │
│  │                                      │                    │
│  │  entity_map: {                       │                    │
│  │    "John Smith" → "PERSON_1"         │                    │
│  │    "Acme Corp"  → "COMPANY_1"        │                    │
│  │    "john@acme.com" → "EMAIL_1"       │                    │
│  │  }                                   │                    │
│  │  (ephemeral — discarded after call)  │                    │
│  └──────────┬───────────────────────────┘                    │
│             │                                                │
│   obfuscated text                                            │
│             │                                                │
└─────────────┼────────────────────────────────────────────────┘
              ▼
       Anthropic API
       (sees PERSON_1, COMPANY_1, EMAIL_1)
              │
              ▼
       response with placeholders
              │
┌─────────────┼────────────────────────────────────────────────┐
│             ▼                                                │
│  ┌──────────────────────────────────────┐                    │
│  │    deobfuscate(response, entity_map) │                    │
│  └──────────┬───────────────────────────┘                    │
│             │                                                │
│   real text restored                                         │
│             │                                                │
│             ▼                                                │
│        SSE stream to client                                  │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 What Gets Obfuscated

| Entity Type | Detection Method | Placeholder Format | Example |
|---|---|---|---|
| Person names | CaseContext seed + NER fallback | `PERSON_1`, `PERSON_2` | "John Smith" → "PERSON_1" |
| Company/org names | CaseContext seed + NER fallback | `COMPANY_1`, `COMPANY_2` | "Acme Corp" → "COMPANY_1" |
| Email addresses | Regex | `EMAIL_1`, `EMAIL_2` | "john@acme.com" → "EMAIL_1" |
| Phone numbers | Regex | `PHONE_1`, `PHONE_2` | "555-123-4567" → "PHONE_1" |
| SSN/EIN | Regex | `[REDACTED]` (irreversible) | "123-45-6789" → "[REDACTED]" |
| Case numbers | Regex | `CASE_1`, `CASE_2` | "BC-2025-12345" → "CASE_1" |
| Filenames | Direct replacement | `Document 1`, `Document 2` | "Smith_Complaint.pdf" → "Document 1" |

### What is NOT obfuscated (preserved for legal accuracy)

- **Dates** — statutes of limitation, filing deadlines, employment dates
- **Dollar amounts** — damages, wages, settlement values
- **Legal citations** — "Cal. Lab. Code § 1102.5", "CACI No. 2505"
- **Legal terms** — "wrongful termination", "FEHA", "retaliation"
- **KB chunks** — public law text (statutes, regulations, agency guidance)

### 4.3 Entity Detection: Two-Layer Strategy

#### Layer 1: CaseContext Seed (LITIGAGENTv2, high precision)

When CaseContext is available (V2.1+), the engine seeds the entity map with **known entities** from case metadata. These are the entities that matter most — party names, attorneys, employer — and they are detected with 100% precision because the attorney has confirmed them.

```python
def seed_from_case_context(self, ctx: CaseContext, map: ObfuscationContext) -> None:
    """Seed known entities from case metadata. Deterministic order."""
    # Parties (most important — these identify the case)
    for i, plaintiff in enumerate(ctx.plaintiffs, 1):
        map.seed("PERSON", plaintiff.name)
    for i, defendant in enumerate(ctx.defendants, 1):
        map.seed("COMPANY" if defendant.is_entity else "PERSON", defendant.name)

    # Attorneys
    for atty in ctx.plaintiff_counsel + ctx.defendant_counsel:
        map.seed("PERSON", atty.name)
        if atty.firm:
            map.seed("COMPANY", atty.firm)

    # Employment relationship
    if ctx.employer_name:
        map.seed("COMPANY", ctx.employer_name)
    if ctx.employee_name:
        map.seed("PERSON", ctx.employee_name)

    # Case number
    if ctx.case_number:
        map.seed("CASE", ctx.case_number)
```

Before CaseContext exists (pre-V2.1), the engine falls back to Layer 2 only.

#### Layer 2: Regex + NER Scan (safety net, moderate precision)

For entities not in the seed list — and for the pre-CaseContext phase — the engine scans text using:

1. **Regex patterns** (high precision): SSN, phone, email, case numbers
2. **spaCy NER** (moderate precision, optional): PERSON, ORG, GPE entities

spaCy's `en_core_web_sm` model (15MB, runs locally, no network calls) provides reasonable NER for English text. It will catch names and companies that aren't in the seed list. It's imperfect on legal text, but it's a safety net — the CaseContext seed handles the critical entities.

**Dependency decision**: Use spaCy directly rather than Presidio. Presidio wraps spaCy but adds complexity (custom recognizer registry, operator framework) that we don't need. We need: (a) regex for structured PII, (b) NER for names. spaCy + 20 lines of regex does both. This follows ISP — don't depend on things you don't need.

### 4.4 Module Structure

```
src/employee_help/privacy/
├── __init__.py
├── engine.py            # ObfuscationEngine: create_context, obfuscate, deobfuscate
├── recognizers.py       # EntityRecognizer: regex patterns + spaCy NER wrapper
└── context.py           # ObfuscationContext: entity map, seed, lookup
```

#### `context.py` — The Ephemeral Entity Map

```python
@dataclass
class ObfuscationContext:
    """Ephemeral bidirectional mapping for one API call lifecycle.

    Created before an API call, used to obfuscate outgoing text
    and deobfuscate incoming text. Discarded after the call completes.
    Never persisted.
    """
    _forward: dict[str, str]     # real value → placeholder
    _reverse: dict[str, str]     # placeholder → real value
    _counters: dict[str, int]    # entity_type → next number

    def seed(self, entity_type: str, real_value: str) -> str:
        """Add a known entity. Returns the placeholder assigned."""

    def add(self, entity_type: str, real_value: str) -> str:
        """Add a discovered entity. Returns the placeholder assigned.
        Idempotent — returns existing placeholder if already mapped."""

    def obfuscate(self, text: str) -> str:
        """Replace all known entities in text with their placeholders.
        Longest-match-first to prevent partial replacements."""

    def deobfuscate(self, text: str) -> str:
        """Replace all placeholders in text with real values.
        Longest-match-first to prevent partial replacements."""
```

**Key behaviors**:
- `seed()` adds entities in caller-defined order (deterministic across calls)
- `add()` appends new entities discovered during scanning
- Replacement uses **longest-match-first** sorting to prevent "Smith" matching inside "Smithfield"
- Replacement uses **word-boundary matching** to prevent "Smith" matching inside "locksmith"
- Both forward and reverse maps updated atomically

#### `recognizers.py` — Entity Detection

```python
class EntityRecognizer:
    """Detects entities in text using regex patterns and optional NER."""

    # Regex patterns (always applied, high precision)
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    CASE_NO_PATTERN = re.compile(r"\b[A-Z]{2,5}[-\s]?\d{2,4}[-\s]?\d{4,}\b")

    # Legal citation whitelist (never obfuscate these)
    CITATION_PATTERN = re.compile(
        r"(?:Cal\.\s*(?:Lab|Gov|Bus|Civ|Evid|Fam|Prob|Pen|Veh)\.\s*Code\s*§\s*[\d.]+|"
        r"CACI\s*No\.\s*\d+|"
        r"\d+\s*C\.F\.R\.\s*§\s*[\d.]+|"
        r"\d+\s*Cal\.\s*(?:App\.)?\s*\d+)"
    )

    def scan(self, text: str) -> list[tuple[str, str]]:
        """Return (entity_type, entity_value) pairs found in text.
        Legal citations are excluded from results."""

    def _scan_regex(self, text: str) -> list[tuple[str, str]]:
        """Regex-based detection for structured PII."""

    def _scan_ner(self, text: str) -> list[tuple[str, str]]:
        """spaCy NER for person and organization names.
        Returns empty list if spaCy is not installed (graceful degradation)."""
```

**spaCy is optional.** If not installed, the engine falls back to regex-only + CaseContext seed. This allows lightweight deployments without the spaCy dependency.

#### `engine.py` — Orchestrator

```python
class ObfuscationEngine:
    """Stateless obfuscation engine for LLM API call boundaries.

    Usage:
        engine = ObfuscationEngine()
        ctx = engine.create_context()

        # Optional: seed with known entities from CaseContext
        engine.seed_from_case_context(case_context, ctx)

        # Scan and obfuscate all text going to the API
        obf_query = engine.obfuscate(query, ctx)
        obf_chunks = [engine.obfuscate(c.content, ctx) for c in case_chunks]

        # ... send to Anthropic ...

        # Deobfuscate the response
        real_response = engine.deobfuscate(response_text, ctx)
        # ctx is discarded (garbage collected)
    """

    def __init__(self, recognizer: EntityRecognizer | None = None) -> None:
        self._recognizer = recognizer or EntityRecognizer()

    def create_context(self) -> ObfuscationContext:
        """Create a fresh, empty context for one API call."""

    def seed_from_case_context(self, case_ctx: CaseContext, ctx: ObfuscationContext) -> None:
        """Seed known entities from LITIGAGENTv2 CaseContext metadata."""

    def obfuscate(self, text: str, ctx: ObfuscationContext) -> str:
        """Scan text for entities, add to context, replace with placeholders."""

    def deobfuscate(self, text: str, ctx: ObfuscationContext) -> str:
        """Replace placeholders with real values."""

    def obfuscate_filename(self, filename: str, index: int) -> str:
        """Replace a real filename with 'Document N'."""
```

### 4.5 Integration Points (Backend Only)

The engine hooks into two places: `CaseChatService` and `ObjectionAnalyzer`. No changes to `LLMClient` — it stays generic and unaware of obfuscation.

#### Integration 1: `CaseChatService` (`src/employee_help/casefile/chat.py`)

**Single-turn (`generate_stream`)**:

```python
def generate_stream(self, query: str, case_id: str) -> ...:
    # 1. Retrieve (local — uses real data for search accuracy)
    case_results, kb_results = self.retrieve_for_case(query, case_id)
    case_notes = self.get_case_notes(case_id)

    # 2. Create obfuscation context
    ctx = self._obfuscation_engine.create_context()

    # 3. Seed from CaseContext if available (V2.1+)
    case_context = self._get_case_context(case_id)  # None pre-V2.1
    if case_context:
        self._obfuscation_engine.seed_from_case_context(case_context, ctx)

    # 4. Scan and obfuscate all case-specific data
    #    KB results are public law — skip obfuscation
    obf_query = self._obfuscation_engine.obfuscate(query, ctx)
    obf_case_results = self._obfuscate_case_results(case_results, ctx)
    obf_case_notes = self._obfuscate_notes(case_notes, ctx)

    # 5. Build prompt with obfuscated data
    system_prompt = self.build_case_system_prompt(obf_case_notes)
    document_blocks, context_order = self.build_case_document_blocks(
        obf_case_results, kb_results  # KB blocks pass through unmodified
    )

    # 6. Call LLM (obfuscated data sent to Anthropic)
    for chunk in self.llm_client.generate_stream(
        system_prompt=system_prompt,
        user_message=obf_query,
        document_blocks=document_blocks,
        mode="attorney",
    ):
        if chunk.text:
            # 7. Deobfuscate each streamed token
            yield self._obfuscation_engine.deobfuscate(chunk.text, ctx)
        if chunk.is_final:
            # ... handle citations, token usage ...
    # ctx is garbage collected — entity map gone
```

**Multi-turn (`generate_stream_multiturn`)**:

For multi-turn, we rebuild the entity map each turn by scanning all data in a consistent order: (1) seed from CaseContext, (2) scan conversation history, (3) scan current query + chunks. This produces deterministic mappings without persisting state.

```python
def generate_stream_multiturn(self, query, case_id, conversation_history, ...):
    case_results, kb_results = self.retrieve_for_case(query, case_id)
    case_notes = self.get_case_notes(case_id)

    # Fresh context, deterministic seeding
    ctx = self._obfuscation_engine.create_context()
    case_context = self._get_case_context(case_id)
    if case_context:
        self._obfuscation_engine.seed_from_case_context(case_context, ctx)

    # Scan history first (ensures same entity → same placeholder as previous turns)
    for turn in conversation_history:
        self._obfuscation_engine.obfuscate(turn["content"], ctx)  # populates map

    # Now obfuscate current data (entities already in map get same placeholders)
    obf_query = self._obfuscation_engine.obfuscate(query, ctx)
    obf_history = [
        {"role": t["role"], "content": self._obfuscation_engine.obfuscate(t["content"], ctx)}
        for t in conversation_history
    ]
    obf_case_results = self._obfuscate_case_results(case_results, ctx)
    obf_case_notes = self._obfuscate_notes(case_notes, ctx)

    # Build and send (same as single-turn)
    # ...
```

**Why this works for multi-turn consistency**: The conversation history contains the deobfuscated text from previous turns. When we scan it, "John Smith" is found again and gets the same placeholder `PERSON_1` because it's encountered in the same order (CaseContext seed → history in order → current data). The entity map is deterministic given the same input.

**Helper methods on CaseChatService**:

```python
def _obfuscate_case_results(
    self, results: list[CaseRetrievalResult], ctx: ObfuscationContext
) -> list[CaseRetrievalResult]:
    """Obfuscate case result content and filenames."""
    obfuscated = []
    for i, result in enumerate(results):
        obfuscated.append(CaseRetrievalResult(
            chunk_id=result.chunk_id,
            file_id=result.file_id,
            case_id=result.case_id,
            content=self._obfuscation_engine.obfuscate(result.content, ctx),
            heading_path=self._obfuscation_engine.obfuscate(result.heading_path, ctx),
            file_type=result.file_type,  # keep (structural, not identifying)
            original_filename=self._obfuscation_engine.obfuscate_filename(
                result.original_filename, i + 1
            ),
            relevance_score=result.relevance_score,
            content_hash=result.content_hash,
        ))
    return obfuscated

def _obfuscate_notes(
    self, notes: list[dict], ctx: ObfuscationContext
) -> list[dict]:
    """Obfuscate note content and filenames."""
    return [
        {
            "content": self._obfuscation_engine.obfuscate(n["content"], ctx),
            "file_id": n["file_id"],
            "filename": self._obfuscation_engine.obfuscate_filename(
                n["filename"], i + 1
            ) if n.get("filename") else None,
        }
        for i, n in enumerate(notes)
    ]
```

#### Integration 2: `ObjectionAnalyzer` (`src/employee_help/discovery/objections/analyzer.py`)

```python
def _analyze_chunk(self, requests, verbosity, party_role, model, posture):
    # System prompt (objection grounds are non-sensitive legal templates)
    system_prompt = self._render_system_prompt(verbosity, party_role, posture)

    # Create obfuscation context
    ctx = self._obfuscation_engine.create_context()

    # Obfuscate discovery request texts
    obf_user_parts = ["Analyze the following discovery requests:\n"]
    for req in requests:
        obf_text = self._obfuscation_engine.obfuscate(req.request_text, ctx)
        obf_user_parts.append(
            f"--- Request No. {req.request_number} ---\n{obf_text}\n"
        )
    user_message = "\n".join(obf_user_parts)

    # API call (obfuscated)
    result = self._llm.generate_with_tools(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=[self._tool_schema],
        model=model,
        mode="attorney",
    )

    # Deobfuscate tool output
    analyses = self._parse_tool_output(result)
    for analysis in analyses:
        analysis["objection_text"] = self._obfuscation_engine.deobfuscate(
            analysis.get("objection_text", ""), ctx
        )

    return analyses
```

#### Integration 3: LITIGAGENTv2 Tier 2 Extraction (Future)

When Tier 2 LLM-assisted metadata extraction is implemented (V2.2), the same engine applies:

```python
def extract_metadata_llm(self, file_content: str, case_id: str):
    ctx = self._obfuscation_engine.create_context()
    # Tier 2 extraction sends file content to LLM for entity/claim extraction
    # The response (extracted entities) is deobfuscated before storing in CaseContext
    obf_content = self._obfuscation_engine.obfuscate(file_content, ctx)
    result = self._llm.generate_with_tools(...)
    # Deobfuscate extracted names before storing
    for entity in result["entities"]:
        entity["name"] = self._obfuscation_engine.deobfuscate(entity["name"], ctx)
```

### 4.6 Dependency on `ObfuscationEngine`

The engine is injected into services via `deps.py`:

```python
# src/employee_help/api/deps.py
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer

_obfuscation_engine: ObfuscationEngine | None = None

def _init_obfuscation_engine() -> ObfuscationEngine:
    global _obfuscation_engine
    if _obfuscation_engine is None:
        recognizer = EntityRecognizer()  # loads spaCy if available
        _obfuscation_engine = ObfuscationEngine(recognizer=recognizer)
    return _obfuscation_engine
```

`CaseChatService.__init__` and `ObjectionAnalyzer.__init__` receive the engine as a constructor parameter. If `None` is passed (e.g., in tests or if privacy is disabled), obfuscation is skipped entirely — the services work exactly as they do today.

### 4.7 LLM Prompt Instruction

The LLM needs to know that placeholders are intentional. Add to `casefile_system.j2`:

```
## Data Privacy
Some identifying information in the case documents has been replaced with
placeholders (e.g., PERSON_1, COMPANY_1). Use these placeholders consistently
in your response. Do not attempt to guess the real names behind placeholders.
```

This is a small addition to the existing system prompt. The LLM will naturally use the placeholders in its response, and our deobfuscation step will replace them with real values before the user sees the response.

### 4.8 Edge Cases

| Edge Case | Handling |
|---|---|
| LLM generates a new placeholder not in the map (e.g., "PERSON_5" when we only seeded 3) | Leave as-is — user sees the placeholder, which is harmless |
| Same name appears as both a person and in a legal citation ("Smith v. Jones") | Legal citation whitelist regex runs BEFORE entity detection. Citations are excluded from the entity scan. |
| Entity spans a chunk boundary ("John\nSmith" split across chunks) | Each chunk is scanned independently. Full names in CaseContext seed handle this — they're matched as whole strings. NER may miss split names, which is acceptable (safety net, not primary defense). |
| Partial name matches ("Smith" inside "Smithfield Foods") | Longest-match-first sorting + word-boundary regex prevents this. "Smithfield Foods" is matched before "Smith". |
| Attorney edits case name/party names after initial upload | No impact — entity map is rebuilt from CaseContext on each API call. Updated names are picked up automatically. |
| Multi-turn: entity map needs to be consistent across turns | Deterministic rebuild: seed from CaseContext, then scan history in order, then current data. Same entities → same placeholders. |
| Streaming: deobfuscation on partial tokens | Buffer tokens until a complete word boundary. Placeholder names (`PERSON_1`) are single tokens — they won't be split mid-stream by the LLM. |

### 4.9 What This Does and Does Not Guarantee

**Does**: Strips person names, company names, emails, phones, SSNs, and case numbers from text sent to Anthropic when the entities are (a) in the CaseContext seed list, or (b) detected by regex/NER.

**Does not**: Guarantee that ALL identifying information is caught. NER is imperfect. An unusual entity not in the seed list and not detected by spaCy will pass through. Contextual information ("the largest employer in Cupertino") may be identifying even without explicit names.

**This is a reasonable-efforts defense, not a guarantee.** It demonstrates that we took affirmative, systematic steps to protect privilege — which is the standard under ABA Formal Opinion 477R and Cal. Rules of Prof. Conduct Rule 1.6.

### 4.10 New Dependencies

| Dependency | Size | Purpose | Required? |
|---|---|---|---|
| `spacy>=3.7,<4.0` | ~10MB (library) | NER engine | Optional (graceful degradation) |
| `en_core_web_sm` | ~15MB (model) | English NER model | Optional |

If spaCy is not installed, the engine uses regex-only + CaseContext seed. This is sufficient for most cases where CaseContext is populated (V2.1+).

Install: `uv pip install spacy && python -m spacy download en_core_web_sm`

Or add to `[web]` optional deps: `spacy>=3.7,<4.0`

### 4.11 Testing Strategy

```
tests/test_privacy/
├── test_context.py          # ObfuscationContext: seed, add, obfuscate, deobfuscate
├── test_recognizers.py      # EntityRecognizer: regex patterns, NER, legal citation whitelist
├── test_engine.py           # ObfuscationEngine: end-to-end obfuscate/deobfuscate
├── test_integration_chat.py # CaseChatService with obfuscation enabled
└── test_integration_objections.py  # ObjectionAnalyzer with obfuscation enabled
```

Key test scenarios:
- Round-trip: `deobfuscate(obfuscate(text)) == text`
- Multi-turn consistency: same entities → same placeholders across turns
- Legal citation preservation: citations are never obfuscated
- Date/dollar preservation: dates and amounts pass through unchanged
- SSN hard redaction: SSNs are replaced and NOT reversible
- Graceful degradation: engine works without spaCy installed
- CaseContext seeding: known entities always get priority placeholders
- Empty text: no crash on empty strings or None
- Filename replacement: real filenames → "Document N"

---

## 5. Phase P1: Informed Consent & Terms

### 5.1 Design Philosophy

We're not trying to scare attorneys. We're giving them the information they need to make an informed decision — the same way any sophisticated legal technology vendor does. The tone should be professional, straightforward, and demonstrate competence. Attorneys respect transparency; they distrust vagueness.

### 5.2 Terms of Service Updates

Add a new **Section 11: "AI Processing of Case Materials"** to the Terms of Service page (`frontend/app/terms/page.tsx`). This section supplements (not replaces) the existing AI limitations language (Section 5), which continues to apply to all AI output. The new section addresses the specific data flows, safeguards, and liability allocation for attorney case workspace tools.

The content for this section is maintained canonically in **Appendix B** of this document. The Terms of Use page renders the following subsections from Appendix B:

- **B.2** (Our Reasonable Efforts) — plain-language descriptions only, not technical details
- **B.3** (What We Cannot Guarantee) — all five limitation points
- **B.4** (Contractual Terms) — full contractual language including assumption of responsibility, limitation of liability, and indemnification

The Terms page should present this as:

```
11. AI Processing of Case Materials

  11.1 Scope — applies to LITIGAGENT case workspace tools
  11.2 How We Protect Your Data — plain-language version of B.2 safeguards
  11.3 Limitations — B.3 limitations in full
  11.4 Your Responsibilities — B.4(a-c) assumption of professional responsibility
  11.5 Limitation of Liability — B.4(d) liability exclusion
  11.6 Indemnification — B.4(e)
  11.7 Acknowledgment — B.4(f)
```

The Privacy Policy page (`/privacy`) receives a companion section covering data flows (what is collected, what is sent to Anthropic, what is never transmitted, Anthropic's retention policy). See Section 5.3 below.

### 5.3 Privacy Policy Updates

Add to the Privacy Policy page (`frontend/app/privacy/page.tsx`):

```
Case File Data Processing

When you use our attorney case workspace tools, we process your data as
follows:

Data we collect and store on our servers:
• Uploaded case files (PDF, Word, Excel, email, images, text)
• Extracted text from those files
• Your notes and annotations
• Chat conversations about your case
• Case metadata (party names, case numbers, claims, dates)
• Generated work product (discovery documents, objection drafts)

Data we send to our AI provider (Anthropic):
• Relevant excerpts from your case files (selected by our search system)
• Your chat questions
• Conversation history within a session
• Discovery request text (for objection analysis)

Before transmission, we apply entity obfuscation to replace identifying
information (names, emails, phone numbers, case numbers) with generic
placeholders. Our AI provider receives "PERSON_1 was employed by COMPANY_1"
rather than actual names.

Data we never send to third parties:
• Your original uploaded files
• Your complete case file text (only relevant excerpts selected by search)
• Social Security numbers or tax identification numbers
• Your account credentials or payment information

Anthropic's data handling:
• API data is not used for model training
• API data is retained for up to 30 days for safety monitoring
• After 30 days, all data is permanently deleted
• Anthropic maintains SOC 2 Type II certification
```

### 5.4 In-App Consent: Use Existing Surfaces, Not New Ones

**We do NOT add a per-case consent banner or a new modal.** The existing ConsentModal (shown once per mode, stored in localStorage) is the consent surface for attorney tools. We update its content to cover AI data processing.

**Current attorney ConsentModal bullets** (in `frontend/components/consent-modal.tsx`):
1. AI-generated, requires verification
2. Not a substitute for legal research
3. No attorney-client relationship, nothing privileged
4. Not reviewed by any person
5. Does not satisfy professional duty

**Updated attorney ConsentModal bullets** — replace the existing 5 bullets with:
1. All output is AI-generated and **requires independent verification** — citations, statutory references, and legal analysis may contain errors.
2. When you use case workspace tools, we **obfuscate identifying information** (names, emails, phone numbers, case numbers) before sending excerpts to our AI provider. No obfuscation system is perfect — some identifying information may not be caught.
3. Your uploaded files are **processed and stored locally** on our servers. Only AI-generated analysis involves a third-party service (Anthropic), which does not train on API data and deletes it within 30 days.
4. You are **solely responsible** for determining whether AI-assisted analysis is appropriate for your matter, including obtaining any required client consent under applicable rules of professional conduct.
5. By continuing, you agree to the Terms of Use, including Section 11 (AI Processing of Case Materials), and accept full responsibility for your use of these tools in connection with any client representation.

**Updated checkbox text**:
"I understand that AI-generated analysis requires verification, that entity obfuscation is not perfect, and that I am responsible for compliance with my professional obligations."

**Updated link text**:
"By continuing you agree to our Terms of Use including our AI data processing practices."

This approach means:
- **No per-case consent** — the modal fires once for attorney mode globally. Adding a second consent per case would create friction without adding legal protection (the Terms already bind the user).
- **No new banner component** — we update existing content, not create new UI.
- **localStorage key unchanged** — `eh-consent-attorney`. Existing users who already consented will see the modal again because we should clear this key when deploying the update (one-time migration via a version check in the consent context).

**Consent version migration**: Add a version number to the localStorage value. When the consent version changes (e.g., from `1` to `2`), the ConsentModal re-appears. This ensures existing users see the updated terms without requiring a separate migration.

```typescript
// In consent-context.tsx
const CONSENT_VERSION = 2; // Bump when consent text changes materially
const stored = localStorage.getItem("eh-consent-attorney");
const hasConsented = stored === String(CONSENT_VERSION);
```

### 5.5 Chat Input Hint

Add a single line below the chat input in the LITIGAGENT workspace (backend provides this as configuration, frontend renders it):

> "Identifying information is obfuscated before AI processing. [Details →]"

This is subtle — a small text line, not a warning. It reassures without alarming.

### 5.6 Backend & Frontend Changes for P1

| File | Change |
|---|---|
| `frontend/app/terms/page.tsx` | Add Section 11 (AI Processing of Case Materials) with safeguards, limitations, and contractual terms from Appendix B |
| `frontend/app/privacy/page.tsx` | Add "Case File Data Processing" section with data flows, obfuscation description, retention policy |
| `frontend/components/consent-modal.tsx` | Update `ATTORNEY_BULLETS` and `ATTORNEY_CHECKBOX` to reflect AI data processing disclosure (see Section 5.4) |
| `frontend/lib/consent-context.tsx` | Add `CONSENT_VERSION` check — bump version to re-trigger consent for existing users |

**No backend changes for P1.** Consent is handled client-side via the existing ConsentModal + localStorage pattern. The Terms and Privacy pages are static content — no API endpoints needed. Per-case acknowledgment tracking (`privacy_acknowledged_at`) is removed from scope; the global consent modal is sufficient legal protection and avoids per-case friction.

---

## 6. Phase P3: Encryption at Rest

### 6.1 Approach: Column-Level Encryption with Fernet

We use the `cryptography` package's Fernet module (AES-128-CBC + HMAC-SHA256, already a transitive dependency via PyJWT) for application-level encryption of sensitive text columns. This is simpler than SQLCipher (which requires replacing the sqlite3 module and C compilation) and sufficient for our threat model.

### 6.2 What Gets Encrypted

| Table | Column | Rationale |
|---|---|---|
| `case_files` | `extracted_text` | Raw case file content |
| `case_files` | `edited_text` | User-modified content |
| `case_notes` | `content` | Attorney annotations |
| `case_chat_turns` | `content` | Conversation content |

These are the columns that contain privileged material at rest. Other columns (filenames, timestamps, IDs) are not encrypted — they're needed for indexing and queries.

### 6.3 Key Management

```python
# Derive encryption key from AUTH_JWT_SECRET
import hashlib
from cryptography.fernet import Fernet
import base64

def _derive_fernet_key(jwt_secret: str) -> bytes:
    """Derive a Fernet key from the JWT secret.
    Uses SHA-256 to produce a 32-byte key, then base64-encode for Fernet."""
    raw = hashlib.sha256(jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)

FERNET = Fernet(_derive_fernet_key(os.environ["AUTH_JWT_SECRET"]))
```

**Trade-off**: Tying encryption to `AUTH_JWT_SECRET` means rotating the JWT secret requires re-encrypting all data. This is acceptable because JWT secret rotation is rare and we can provide a migration script.

### 6.4 Implementation

Create a thin wrapper in `src/employee_help/privacy/encryption.py`:

```python
class FieldEncryptor:
    """Transparent encryption/decryption for SQLite text columns."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        return self._fernet.decrypt(ciphertext.encode()).decode()
```

Integrate into `CaseStorage`:

```python
class CaseStorage:
    def __init__(self, conn, encryptor: FieldEncryptor | None = None):
        self._enc = encryptor

    def _encrypt(self, text: str | None) -> str | None:
        return self._enc.encrypt(text) if self._enc else text

    def _decrypt(self, text: str | None) -> str | None:
        return self._enc.decrypt(text) if self._enc else text

    def update_case_file_text(self, file_id, *, extracted_text, edited_text, ...):
        # Encrypt before writing
        enc_extracted = self._encrypt(extracted_text)
        enc_edited = self._encrypt(edited_text)
        # ... SQL INSERT with encrypted values ...

    def get_case_file(self, file_id) -> CaseFile | None:
        # ... SQL SELECT ...
        # Decrypt after reading
        file.extracted_text = self._decrypt(file.extracted_text)
        file.edited_text = self._decrypt(file.edited_text)
        return file
```

### 6.5 Migration

Existing data needs a one-time migration. Add a CLI command:

```
employee-help encrypt-case-data [--dry-run]
```

This reads all case files, notes, and chat turns, encrypts the relevant columns, and writes them back. Idempotent — detects already-encrypted values and skips them.

### 6.6 Impact on Search

Encrypted columns cannot be searched with SQL `LIKE`. This is fine because:
- Case file text is searched via LanceDB vector/FTS index (not SQLite)
- Chat turns are retrieved by session_id (not searched by content)
- Notes are retrieved by case_id and file_id (not searched by content)

LanceDB embeddings store the `content` field in plaintext (needed for BM25 FTS). This is a trade-off: we protect the database but the vector store retains searchable text. A future enhancement could encrypt the LanceDB content column and rely on vector-only search, but this would degrade retrieval quality (no BM25 component).

---

## 7. Implementation Schedule

### Phase P2: Obfuscation Engine — COMPLETE (2026-03-15)

289 tests across 7 test files. Phone regex fix applied (parenthesized numbers).

| Gate | Task | Files | Status |
|---|---|---|---|
| P2.1 | `ObfuscationContext` class with seed/add/obfuscate/deobfuscate | `privacy/context.py` | DONE (48 tests) |
| P2.2 | `EntityRecognizer` with regex patterns + legal citation whitelist | `privacy/recognizers.py` | DONE (73 base tests) |
| P2.3 | spaCy NER integration (optional, graceful degradation) | `privacy/recognizers.py` | DONE (99 total tests) |
| P2.4 | `ObfuscationEngine` orchestrator + filename obfuscation | `privacy/engine.py` | DONE (44 tests) |
| P2.5 | Cross-cutting tests (round-trip, edge cases, citation whitelist) | `tests/test_privacy/test_cross_cutting.py` | DONE (41 tests) |
| P2.6 | Integrate into `CaseChatService` (single-turn + multi-turn) | `casefile/chat.py`, `api/deps.py` | DONE (23 tests) |
| P2.7 | Integrate into `ObjectionAnalyzer` | `discovery/objections/analyzer.py`, `objection_routes.py` | DONE (14 tests) |
| P2.8 | Update `casefile_system.j2` with privacy instruction | `config/prompts/casefile_system.j2` | DONE |
| P2.9 | E2E integration tests (chat + objection paths) | `tests/test_privacy/test_e2e_obfuscation.py` | DONE (20 tests) |

**Gate check** — all verified via E2E tests:
1. Anthropic receives obfuscated text (mock LLM call args) — PASS
2. User receives deobfuscated response with real names — PASS
3. Multi-turn consistency holds across 3+ turns (4-turn test) — PASS
4. Legal citations in response are preserved correctly — PASS

### Phase P1: Informed Consent & Terms — COMPLETE (2026-03-15)

| Gate | Task | Files | Status |
|---|---|---|---|
| P1.1 | Update Terms of Service page — add Section 11 (AI Processing) with safeguards, limitations, contractual terms from Appendix B | `frontend/app/terms/page.tsx` | DONE |
| P1.2 | Update Privacy Policy page — add Case File Data Processing section | `frontend/app/privacy/page.tsx` | DONE |
| P1.3 | Update ConsentModal attorney bullets + checkbox text (see Section 5.4) | `frontend/components/consent-modal.tsx` | DONE |
| P1.4 | Add consent version check to re-trigger modal for existing users | `frontend/lib/consent-context.tsx` | DONE |
| P1.5 | Add chat input hint line ("Identifying info is obfuscated...") | `frontend/components/litigagent/chat-drawer.tsx` | DONE |
| P1.6 | Review pass — verify all links between surfaces (modal → Terms, footer → Privacy, hint → Terms) | Manual verification | DONE |

### Phase P3: Encryption at Rest — COMPLETE (2026-03-15)

| Gate | Task | Files | Status |
|---|---|---|---|
| P3.1 | `FieldEncryptor` class with Fernet | `privacy/encryption.py` | DONE (18 tests) |
| P3.2 | Integrate into `CaseStorage` (encrypt on write, decrypt on read) | `storage/case_storage.py` | DONE (20 tests) |
| P3.3 | Wire `FieldEncryptor` into `deps.py` | `api/deps.py` | DONE |
| P3.4 | Migration CLI command `encrypt-case-data` | `cli.py` | DONE |
| P3.5 | Unit + integration tests | `tests/test_privacy/test_encrypt_migration.py` | DONE (15 tests) |
| P3.6 | Verify LanceDB search still works (content not encrypted there) | `tests/test_privacy/test_lancedb_not_encrypted.py` | DONE (10 tests) |

### Deferred (Not Scheduled)

| Phase | Reason |
|---|---|
| P4: Transmission audit trail | Nice-to-have, not required for launch. Adds UI complexity and a new endpoint. Revisit when attorneys request it. |
| P5: Auto-expiry | Requires background task infrastructure. Low ROI — attorneys can delete cases manually. |
| P6: Self-hosted LLM | Requires GPU infrastructure, model evaluation, prompt re-tuning. Different product tier, different business decision. |

---

## Appendix A: File-by-File Audit

### Files That Send Data to Anthropic

| File | Function | Data Sent |
|---|---|---|
| `src/employee_help/generation/llm.py` | `generate_stream()`, `generate_stream_multiturn()`, `generate_with_tools()` | System prompt, user message, document blocks, tools, history |
| `src/employee_help/casefile/chat.py` | `generate_stream()`, `generate_stream_multiturn()` | Case file chunks, KB chunks, attorney notes, query, history |
| `src/employee_help/discovery/objections/analyzer.py` | `_analyze_chunk()` | Discovery request text |
| `src/employee_help/generation/service.py` | `generate_stream()` | User query, KB chunks (homepage chat only) |
| `src/employee_help/api/routes.py` | `ask_stream()`, `intake_summary_stream()` | User query, KB chunks (homepage only) |

### Files That Store Sensitive Data Locally

| File | Storage | Data | Encrypted (P3) |
|---|---|---|---|
| `storage/case_storage.py` | SQLite | `extracted_text`, `edited_text`, note `content`, chat `content` | **Yes** |
| `casefile/case_vector_store.py` | LanceDB | Chunk content + embeddings | No (needed for FTS) |
| `feedback/store.py` | SQLite | Query hashes (SHA256), no full text | N/A |
| `auth/storage.py` | SQLite | Users, sessions | N/A |

### Files Modified by Privacy Implementation

| File | Phase | Changes |
|---|---|---|
| `src/employee_help/privacy/__init__.py` | P2 | New module |
| `src/employee_help/privacy/context.py` | P2 | ObfuscationContext |
| `src/employee_help/privacy/recognizers.py` | P2 | EntityRecognizer |
| `src/employee_help/privacy/engine.py` | P2 | ObfuscationEngine |
| `src/employee_help/privacy/encryption.py` | P3 | FieldEncryptor |
| `src/employee_help/casefile/chat.py` | P2 | Obfuscation hooks in generate_stream/_multiturn |
| `src/employee_help/discovery/objections/analyzer.py` | P2 | Obfuscation hooks in _analyze_chunk |
| `src/employee_help/api/deps.py` | P2, P3 | ObfuscationEngine + FieldEncryptor singletons |
| `src/employee_help/storage/case_storage.py` | P3 | encrypt/decrypt on sensitive columns |
| `config/prompts/casefile_system.j2` | P2 | Privacy instruction for placeholders |
| `frontend/app/terms/page.tsx` | P1 | Section 11: AI Processing of Case Materials (safeguards, limitations, contractual terms) |
| `frontend/app/privacy/page.tsx` | P1 | Case File Data Processing section (data flows, retention) |
| `frontend/components/consent-modal.tsx` | P1 | Updated attorney bullets + checkbox text (obfuscation, responsibility, Terms link) |
| `frontend/lib/consent-context.tsx` | P1 | Consent version check (re-trigger modal for existing users on terms update) |
| `frontend/components/litigagent/chat-drawer.tsx` | P1 | Inline hint below chat input ("Identifying info is obfuscated...") |
| `pyproject.toml` | P2 | Optional spacy dependency |

---

## Appendix B: Legal Framework & Liability

### B.1 The Rule: ABA Formal Opinion 477R

ABA Formal Opinion 477R (May 2017) establishes the standard for attorney use of technology when handling client confidential information. In plain terms:

**What it says**: Attorneys have an ethical duty to make "reasonable efforts" to prevent the inadvertent or unauthorized disclosure of confidential client information when using technology. This is not a guarantee of perfection — it is a standard of care. The Opinion identifies factors for assessing reasonableness: the sensitivity of the information, the likelihood of disclosure, the cost and difficulty of additional safeguards, and the extent to which safeguards adversely affect the attorney's ability to represent clients.

**What it does NOT say**: It does not prohibit attorneys from using cloud services, AI tools, or third-party processors. It does not require zero-risk technology. It requires informed, competent decision-making and affirmative protective measures.

**Related authority**:
- **ABA Model Rule 1.6(c)**: "A lawyer shall make reasonable efforts to prevent the inadvertent or unauthorized disclosure of, or unauthorized access to, information relating to the representation of a client."
- **ABA Formal Opinion 512 (2024)**: Extends these duties explicitly to generative AI tools. Attorneys must understand how AI tools process client data, obtain informed client consent where appropriate, and supervise AI output.
- **Cal. Rules of Prof. Conduct, Rule 1.6(a)**: California's duty of confidentiality, substantially similar to Model Rule 1.6.
- **Cal. Evid. Code § 952**: Defines "confidential communication" between client and lawyer.
- **Cal. Evid. Code § 912(a)**: Waiver of privilege by disclosure — but consent-based exceptions apply when the client authorizes disclosure to specific agents or services.

### B.2 Our Reasonable Efforts: What We Do

We structure our system so that the vast majority of data processing happens locally, and the narrow channel where data reaches a third party (Anthropic's API) is protected by entity obfuscation. Here is what we do, in both plain and technical terms:

#### 1. Local-first architecture

**In plain terms**: When you upload a complaint, pay stubs, emails, or any other file, we extract the text, run OCR on scanned documents, build a searchable index, and store everything — all on our own servers. None of these steps involve any third party. Your files never leave our infrastructure.

**In technical terms**: File extraction (pdfplumber, python-docx, openpyxl, stdlib email/csv, pytesseract+Pillow), embedding generation (sentence-transformers BGE-base-en-v1.5, local CPU inference), vector search (LanceDB, embedded database), full-text search (LanceDB FTS), and primary storage (SQLite WAL mode) all run as local processes with zero outbound network calls. The only network egress for case data is the Anthropic Claude API, described below.

#### 2. Entity obfuscation at the API boundary

**In plain terms**: Before we send any text to our AI provider, we automatically scan it for identifying information — party names, attorney names, company names, email addresses, phone numbers, and case numbers — and replace each one with a generic placeholder like `PERSON_1` or `COMPANY_1`. The AI sees "PERSON_1 was employed by COMPANY_1 from 2019 to 2025" instead of real names. When the AI responds using those same placeholders, we swap the real names back in before you see the answer.

**In technical terms**: The `ObfuscationEngine` creates an ephemeral `ObfuscationContext` (a bidirectional string map) that exists only for the duration of a single API request-response cycle. It is never persisted, never logged, and never stored in the database. Entity detection uses two layers: (1) CaseContext seeding — known parties, attorneys, and employers extracted from case metadata are matched with 100% precision; (2) regex patterns for structured PII (SSN, phone, email, case numbers) and optional spaCy NER for names not in the seed list. Replacement uses longest-match-first sorting with word-boundary matching to prevent partial replacements. Legal citations, dates, dollar amounts, and statutory references are whitelisted and never obfuscated — they are public law and essential for accurate legal analysis.

#### 3. CaseContext seeding for high-accuracy obfuscation

**In plain terms**: When you upload a complaint and we extract the party names, case number, and attorney information, that information becomes a "seed list" for obfuscation. Because we already know exactly who the parties are, we can find and replace those names with near-perfect accuracy — even if a name appears in an unusual format or context.

**In technical terms**: `CaseContext` metadata (from LITIGAGENTv2 Tier 1/Tier 2 extraction, validated or corrected by the attorney in the Case Info view) is passed to `ObfuscationEngine.seed_from_case_context()` before each API call. Seeded entities are matched as whole strings before NER scanning, ensuring that the most sensitive entities (case-identifying parties) are handled deterministically rather than probabilistically.

#### 4. Encryption at rest

**In plain terms**: Your case files, extracted text, notes, and chat history are encrypted in our database. Even if someone gained unauthorized access to the raw database file, the content would be unreadable without the encryption key.

**In technical terms**: Application-level column encryption using Fernet (AES-128-CBC + HMAC-SHA256) on `extracted_text`, `edited_text`, note `content`, and chat turn `content` columns. Key derived from server-side secret via SHA-256. Encryption is transparent — applied on write, reversed on read — and does not affect search (which uses the separate LanceDB vector/FTS index).

#### 5. Transparent disclosure

**In plain terms**: We tell you how your data is processed before you use any AI feature. This information is available in our Terms of Use and Privacy Policy, and is summarized in the attorney consent acknowledgment when you first use the case workspace. We believe you are entitled to know exactly how this works before you decide whether it meets your needs.

**In technical terms**: Disclosure surfaces include the Terms of Use page (`/terms`, Section 11), Privacy Policy page (`/privacy`, Case File Data Processing section), the existing attorney ConsentModal (updated to reflect AI data processing), and an inline hint below the case chat input. All disclosures link to the canonical Terms and Privacy pages. No information is hidden behind separate screens or buried in fine print.

#### 6. No-training guarantee

**In plain terms**: Anthropic (our AI provider) does not use any data sent through their API to train their AI models. This is a contractual commitment documented in their commercial API terms, not just a policy statement.

**In technical terms**: Anthropic's commercial API terms explicitly exclude API inputs and outputs from model training. This applies to all data sent via the Messages API, which is the sole integration point. Anthropic maintains SOC 2 Type II certification for their API infrastructure.

#### 7. Time-limited retention by AI provider

**In plain terms**: Anthropic retains API data for up to 30 days for trust and safety monitoring (e.g., preventing misuse of their models), then permanently deletes it. During that 30-day window, the data they hold is the obfuscated version — `PERSON_1`, `COMPANY_1` — not the real names.

**In technical terms**: Anthropic's API data retention policy is 30 days for trust and safety review, after which data is permanently deleted. Zero Data Retention (ZDR) agreements are available for enterprise-tier customers, which we may pursue as the product scales. The data retained during the 30-day window has already been processed by our obfuscation engine, so it contains placeholders rather than identifying information (with the caveats noted in B.3 below).

### B.3 What We Cannot Guarantee: Honest Limitations

No obfuscation system is perfect, and we do not claim otherwise. Attorneys evaluating this tool should understand these limitations:

1. **NER is imperfect.** Our natural language processing may not catch every name, especially unusual names, names that appear only in context ("the VP of Marketing"), or names embedded in non-standard formatting. The CaseContext seed handles known parties with high accuracy, but entities not in the seed list and not detected by pattern matching or NER will pass through to the AI provider.

2. **Contextual identification is possible.** Even with all names replaced, the factual pattern of a case may be identifying. "The largest ride-sharing company in San Francisco terminated its head of diversity in 2024 after she filed an internal complaint" contains no names but may be identifying. We do not attempt to obfuscate facts, dates, locations, or circumstances — doing so would destroy the legal analysis that makes the tool useful.

3. **AI provider data retention.** During the 30-day retention window, Anthropic holds obfuscated text. While this text contains placeholders rather than real names, it still contains the factual substance of the case. An Anthropic employee conducting a trust and safety review could theoretically read this content. We consider this risk low (Anthropic is SOC 2 certified, and reviews are conducted under strict access controls), but it is not zero.

4. **Encryption does not protect against application-level access.** Our encryption at rest protects against database file theft, but data is necessarily decrypted in application memory during normal use. A compromise of the application server would expose decrypted data.

5. **This is a best-efforts system, not a privilege shield.** We provide tools that help attorneys meet their duty of reasonable care. We do not — and cannot — guarantee that use of this system will prevent a finding of privilege waiver in any particular proceeding. Courts evaluate privilege claims based on the totality of circumstances, including the attorney's independent judgment about what safeguards were appropriate for the matter at hand.

### B.4 Contractual Terms: Allocation of Risk

The following provisions are incorporated into our Terms of Use (Section 11: AI Processing of Case Materials) and govern the use of LITIGAGENT case workspace tools:

#### Assumption of Professional Responsibility

You acknowledge and agree that:

(a) **Professional judgment.** The decision to upload client materials to this Service, and to use AI-assisted analysis of those materials, is an exercise of your independent professional judgment. You are solely responsible for determining whether such use is appropriate given the nature and sensitivity of the matter, the client's expectations, applicable rules of professional conduct, and any court orders or protective orders that may restrict the disclosure of case materials.

(b) **Client consent.** Where applicable rules of professional conduct or ethics opinions require client consent for the use of AI-assisted tools in connection with a representation, you are solely responsible for obtaining such consent before uploading client materials. We do not verify whether you have obtained client consent.

(c) **Supervision of output.** All AI-generated analysis, objections, discovery requests, and other work product require your independent review and professional judgment before use. You are responsible for verifying the accuracy, completeness, and appropriateness of all output.

#### Limitation of Liability for Confidentiality Claims

(d) **No liability for confidentiality-related claims.** To the fullest extent permitted by applicable law, the operators of this Service shall not be liable for any claim, loss, damage, disciplinary proceeding, malpractice action, bar complaint, or other consequence arising from or relating to: (i) an alleged breach of attorney-client privilege, work product protection, or duty of confidentiality resulting from your use of the Service; (ii) the failure of our entity obfuscation system to detect or replace any particular item of identifying information; (iii) any determination by a court, tribunal, or disciplinary body that your use of AI-assisted tools was inconsistent with your professional obligations; or (iv) the retention, processing, or potential exposure of case data by our third-party AI provider during the data retention period described in our Privacy Policy.

(e) **Indemnification.** You agree to indemnify, defend, and hold harmless the operators of this Service from and against any claims, damages, losses, costs, and expenses (including reasonable attorneys' fees) arising from or relating to your use of the Service in connection with a client representation, including any claim that such use breached a duty of confidentiality, privilege, or professional conduct.

#### Acknowledgment

(f) **Informed use.** By using the LITIGAGENT case workspace tools, you acknowledge that you have read and understood our Privacy Policy (including the description of entity obfuscation, data flows, and third-party processing), that you understand the limitations of automated obfuscation as described herein, and that you accept full responsibility for determining whether the safeguards we provide are sufficient for your particular use case.

### B.5 How This Should Be Communicated to Users

Our goal is to be **reassuring through specificity** — attorneys respect vendors who explain exactly how things work and are honest about limitations. The tone should convey competence and transparency, not anxiety.

**Reassurance (plain and technical terms):**
- The Privacy Policy and Terms of Use contain both plain-language explanations and technical specifics of our data protection measures. Attorneys should be able to read these and understand exactly what happens when they press "send."
- The system architecture is described in enough detail that a technically sophisticated attorney (or their firm's IT security team) can evaluate whether it meets their requirements.

**Liability protection (contractual terms):**
- The assumption of professional responsibility, limitation of liability, and indemnification clauses in Section B.4 are drafted in standard commercial contract language. They appear in the Terms of Use, which the attorney agrees to upon account creation and re-acknowledges via the case workspace consent flow.
- These terms do not override the plain-language descriptions — they operate alongside them. An attorney who reads "no obfuscation system is perfect" and "you are responsible for determining whether this is appropriate" has been given fair notice.

**What we do NOT do:**
- We do not bury the limitations. They appear in the same section as the safeguards.
- We do not use scare tactics or alarmist language. The tone is factual.
- We do not disclaim all responsibility for building a bad product. We stand behind the quality of our engineering. What we disclaim is responsibility for the attorney's independent professional judgment about whether this tool is appropriate for their specific situation.

### B.6 Disclosure Surface Inventory

To avoid modal/banner proliferation, all privacy information flows through a small number of **evergreen, canonical surfaces**:

| Surface | What It Contains | When User Sees It |
|---|---|---|
| **Terms of Use** (`/terms`) | Full legal terms including Section 11 (AI Processing of Case Materials) with liability, indemnification, and assumption of responsibility | Linked from consent modal, disclaimer footer, case workspace |
| **Privacy Policy** (`/privacy`) | Full privacy policy including Case File Data Processing section, data flows, Anthropic's retention policy | Linked from consent modal, disclaimer footer, case workspace |
| **Attorney ConsentModal** (existing) | Updated bullet points reflecting AI data processing + obfuscation. Checkbox acknowledgment. Links to Terms. | First time attorney mode is used (stored in localStorage) |
| **Disclaimer footer** (existing) | One-line disclaimer with links to Terms + Privacy | Every page, always visible |
| **Chat input hint** (new, inline text) | "Identifying info is obfuscated before AI processing. [Terms →]" | Below case chat input, always visible, not dismissible |

**What we do NOT add:**
- No new modals
- No new banner components
- No new pages
- No per-case consent flow (the existing ConsentModal covers attorney mode globally; we do not add a second consent per case)
- No pop-ups, toasts, or interstitials

The ConsentModal attorney text is updated once. The Terms and Privacy pages are updated once. The chat input hint is a single line of small text. All three surfaces link to the same canonical Terms and Privacy pages.
