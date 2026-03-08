# LITIGAGENT: Case File Ingestion Engine

> **Your AI associate that has read every document, remembers every detail, and turns case files into work product.**

**Status**: PLANNING
**Created**: 2026-03-06
**Author**: Product & Engineering
**Dependencies**: Phase 2 (RAG), Phase 3B (Web), Phase O.1 (Objection Drafter)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Market Analysis & Competitive Landscape](#2-market-analysis--competitive-landscape)
3. [Product Vision & Strategy](#3-product-vision--strategy)
4. [User Jobs & Use Cases](#4-user-jobs--use-cases)
5. [Architecture & Technical Design](#5-architecture--technical-design)
6. [UI/UX Design](#6-uiux-design)
7. [Data Model & Storage Schema](#7-data-model--storage-schema)
8. [File Processing Pipeline](#8-file-processing-pipeline)
9. [API Design](#9-api-design)
10. [Retrieval & Chat Integration](#10-retrieval--chat-integration)
11. [Workflow Integration Points](#11-workflow-integration-points)
12. [Security & Privilege](#12-security--privilege)
13. [Phasing & MVP Strategy](#13-phasing--mvp-strategy)
14. [Testing Strategy](#14-testing-strategy)
15. [Metrics & Success Criteria](#15-metrics--success-criteria)
16. [Risk Assessment](#16-risk-assessment)
17. [Future Roadmap](#17-future-roadmap)

---

## 1. Executive Summary

### The Problem

Attorneys receive case files from clients, carriers, opposing counsel, and courts in dozens of formats — PDFs, emails, Word documents, spreadsheets, scanned images, and case filings. Today's workflow is fundamentally broken:

1. **Ingestion is manual.** Associates spend hours reading, re-reading, and organizing documents.
2. **Analysis is disconnected from action.** The tools for *reading* documents are completely separate from the tools for *drafting* work product (demand letters, discovery, case analyses, settlement agreements).
3. **Context lives in the attorney's head.** Critical case knowledge — who the parties are, which documents matter, what the theory of the case is — is never captured in a structured, reusable way.
4. **No single source of truth.** Files scatter across email, shared drives, and case management systems. There's no unified, searchable, AI-ready representation of "the case."

### The Solution

LITIGAGENT is a **case file ingestion engine** — a three-panel interface where attorneys:

- **Panel 1 (Files):** Drag and drop entire case folders. See every file, its processing status, and navigate instantly.
- **Panel 2 (Extracted Text):** View a single, unified, editable plain-text representation of all case documents. Verify OCR quality. Fix extraction errors. Click a file in Panel 1 to jump to its content.
- **Panel 3 (Attorney Notes):** Capture judgment, context, and analysis that only the attorney knows — party relationships, strategic considerations, document importance. These notes become AI context.

After ingestion, the attorney can **chat with their case** or **enter any workflow** — and the AI has read every document, understands the attorney's notes, and can cite specific files when generating work product.

### Why This Wins

| Competitor | What They Do | What They Miss |
|-----------|-------------|---------------|
| **FilevineAI** | Chat with case data inside Filevine | Locked to Filevine ecosystem. No standalone ingestion. No workflow output. |
| **CoCounsel** | Document Q&A and summarization | Enterprise pricing ($$$). No file-to-workflow pipeline. No attorney notes layer. |
| **Harvey** | Document analysis and drafting | General-purpose. No case-level file organization. No unified text view. |
| **Supio** | Medical chronologies for PI | Personal injury only. No general litigation support. |
| **Everlaw/Relativity** | eDiscovery at scale (10M+ docs) | Overkill for case prep. $10K+/month. Not designed for work product generation. |
| **ChronoVault** | Timeline generation from case files | Timeline-focused only. No chat. No workflow integration. |
| **Lawdify** | OCR + organize for construction | Construction disputes only. No LLM integration. |
| **Briefpoint** | Discovery response automation | Starts at discovery, not at ingestion. No case-level context. |

**LITIGAGENT's contrarian bet (Zero to One):** The value isn't in any single feature — it's in the *pipeline*. No competitor connects ingestion → verification → annotation → chat → workflow in a single, seamless experience. Every other tool handles one piece. We handle the full arc.

---

## 2. Market Analysis & Competitive Landscape

### 2.1 Market Sizing

| Segment | Size | Willingness to Pay | Priority |
|---------|------|-------------------|----------|
| **California litigation attorneys** | ~45K active litigators | High ($200-500/mo for productivity tool) | PRIMARY |
| **California employment law attorneys** | ~8K specialists | Very high (existing audience) | BEACHHEAD |
| **U.S. litigation attorneys** (expansion) | ~400K | High | PHASE 2 |
| **Solo/small firm** (1-10 attorneys) | 75% of CA firms | Medium ($50-200/mo) | KEY SEGMENT |
| **Mid-size firm** (10-100 attorneys) | 15% of CA firms | High ($200-500/seat/mo) | GROWTH |
| **Insurance defense / PI firms** | High volume, document-heavy | Very high | IDEAL FIT |

**TAM (California litigators):** ~45K × $300/mo × 12 = **$162M ARR**
**SAM (employment + PI + insurance defense):** ~15K × $300/mo × 12 = **$54M ARR**
**SOM (Year 1 target):** 200 attorneys × $200/mo × 12 = **$480K ARR**

### 2.2 Competitive Deep-Dive

#### Tier 1: Direct Competitors (Case File + AI)

**FilevineAI** — "Chat with your case"
- Strengths: Deep integration with Filevine case management. Access to 100% of matter data. RAG-powered.
- Weaknesses: Requires Filevine subscription ($39-79/user/mo). Cannot ingest external files independently. No editable text extraction view. No attorney notes layer.
- Pricing: Add-on to Filevine subscription.
- *Our advantage:* Standalone tool. Works with any case management system. Three-panel ingestion UX.

**Supio** — AI for Personal Injury
- Strengths: Medical chronology automation. Bill reconciliation. "Chat with your case" interface. Strong PI-specific features (Exhibit Builder, Tabular Analysis). Knowledge Bases feature (firm-wide reference library).
- Weaknesses: PI-only. No general litigation. No editable extraction view. No standalone file ingestion.
- Pricing: Subscription based on case volume.
- *Our advantage:* All litigation types. Employment law depth. File-to-workflow pipeline.

**ChronoVault (NexLaw)** — Timeline from case files
- Strengths: Strong OCR (PDFs, emails, scanned images). Automatic timeline generation. Interactive filtering. Court-ready export.
- Weaknesses: Timeline-only output. No chat. No workflow integration. No attorney notes.
- *Our advantage:* Chat + multiple workflows, not just timelines.

#### Tier 2: Adjacent Competitors (Document AI, no case-level ingestion)

**CoCounsel (Thomson Reuters)** — Legal AI assistant
- 79.5% avg benchmark score. Document Q&A at 89.6%. Timeline creation, document comparison, inline citations.
- Weakness: Enterprise pricing. No case-level file organization. Focused on Westlaw/Practical Law content, not user-uploaded case files.

**Harvey AI** — Legal AI platform
- 94.8% document Q&A accuracy (highest in benchmarks). Strong summarization and analysis.
- Weakness: General-purpose legal AI. No case file management. No three-panel ingestion UX.

#### Tier 3: eDiscovery (Massive Scale, Wrong Problem)

**Everlaw** — Cloud eDiscovery
- Deep Dive: ask questions across millions of documents. Coding Suggestions. Writing Assistant. Clustering.
- Weakness: Per-GB pricing. Designed for eDiscovery (production, privilege review), not case prep. Overkill for 100-file case.

**Relativity** — Enterprise eDiscovery
- aiR for Review: automated document analysis. Massive scale.
- Weakness: Enterprise-only. $10K+/month. Not designed for attorney work product.

#### Tier 4: Emerging (ABA TECHSHOW 2026 Startups)

**Lawdify** — OCRs, parses, organizes construction documents by parties/dates/issues. Generates claim packs with fact-checked timelines.
**Litmas** — AI litigation workflow management. Integrates evidence organization with drafting.
**TwinCounsel** — AI teammate in lawyer's inbox. Builds case context from emails and attachments.

### 2.3 Key Market Insights

1. **Legal AI adoption surged from 37% (2024) to 80% (2025).** The market is ready.
2. **RAG hallucination is a real concern.** Lexis+ AI and Westlaw AI hallucinate 17-33% of the time. Our editable extraction view and citation-to-source linking directly address trust.
3. **"Chat with your case" is becoming table stakes.** FilevineAI, Supio, and Harvey all offer it. The differentiator is what comes *before* (ingestion quality) and *after* (workflow output).
4. **The gap is ingestion → workflow.** Every competitor handles either ingestion OR workflow. None connect the full pipeline.
5. **Attorneys want to verify, not blindly trust.** The editable middle panel is a trust-building feature that no competitor offers.

### 2.4 Positioning Statement

> **For litigation attorneys** who receive stacks of case files from clients and carriers,
> **LITIGAGENT** is a case file ingestion engine
> **that** converts any document into searchable, editable, AI-ready text and connects it directly to legal workflows,
> **unlike** FilevineAI (locked ecosystem), CoCounsel (no file management), or Everlaw (overkill pricing),
> **because** we are the only tool that connects ingestion → verification → annotation → chat → work product in a single experience.

---

## 3. Product Vision & Strategy

### 3.1 Jobs-to-be-Done Analysis

#### Primary Job: "Help me understand this case quickly so I can do the work"

**Job Map (8 steps of the universal job):**

| Step | Attorney Action | LITIGAGENT Role |
|------|----------------|-----------------|
| 1. **Define** | "I need to review 100 files for this new case" | Case creation, file drop zone |
| 2. **Locate** | "Where are all the relevant files?" | Drag-and-drop folders, batch upload |
| 3. **Prepare** | "I need these in a readable format" | OCR, text extraction, format normalization |
| 4. **Confirm** | "Did the extraction work correctly?" | Editable middle panel, OCR confidence indicators |
| 5. **Execute** | "Let me read and understand these documents" | Unified text view, search, navigation |
| 6. **Monitor** | "What's important? What am I missing?" | AI-suggested highlights, cross-reference detection |
| 7. **Modify** | "I need to add context the files don't capture" | Attorney notes panel, file-specific annotations |
| 8. **Conclude** | "Now I need to draft the demand letter / discovery / analysis" | Chat interface, workflow entry points |

#### Forces of Progress

| Force | Description | Feature Response |
|-------|-------------|-----------------|
| **Push (away from current)** | Hours spent manually reading and organizing files. Context lost between reading and drafting. Associates forget details across 100+ files. | Instant extraction, unified view, AI memory |
| **Pull (toward LITIGAGENT)** | Instant file processing. Editable verification. Case-level chat. Direct workflow entry. | Three-panel UX, chat, workflow buttons |
| **Anxiety (about switching)** | "Will it extract correctly?" "Is my data secure?" "Will it miss something?" "Can I trust AI with privileged files?" | Editable text (verify), OCR confidence, encryption, on-premise option |
| **Habit (current behavior)** | Reading PDFs in Acrobat. Notes in Word/legal pads. Manual organization in case management. | Must be faster than current workflow from minute one. Zero learning curve. |

### 3.2 Value Proposition Canvas

**Pain Relievers:**
- Eliminates hours of manual document reading and re-reading
- Captures attorney judgment/context alongside files (currently lost in attorney's head)
- Prevents "I know I read this somewhere" moments — everything searchable
- Reduces context-switching between reading tool and drafting tool to zero

**Gain Creators:**
- Ask any question about the case and get an answer with file citations in seconds
- Transition from "I've read the files" to "Here's a draft demand letter" with one click
- New associates can get up to speed on a case in minutes, not days
- Firm builds institutional case knowledge (notes persist, AI learns context)

### 3.3 Product-Led Growth Strategy

**Time-to-Value:** < 2 minutes (drag files → see extracted text → ask first question)

**Freemium Wedge:**
- Free tier: 3 cases, 25 files per case, 50MB total, basic chat (5 questions/case)
- Pro tier: Unlimited cases/files, 500MB per case, unlimited chat, all workflows
- Firm tier: Team sharing, case templates, admin controls, priority processing

**Viral Loop:**
- Attorney uses LITIGAGENT → shares case with co-counsel → co-counsel sees the value → signs up
- Attorney generates work product → opposing counsel asks "how did you draft this so fast?" → referral

**Activation Metric:** First successful chat question answered with file citation within first session.

---

## 4. User Jobs & Use Cases

### 4.1 Core Use Cases

#### UC-1: Insurance Defense Discovery Preparation
> An associate receives 100 files from an insurance carrier: police reports, medical records, correspondence, the insured's personnel file, witness statements, and the complaint. The associate needs to prepare discovery (interrogatories, RFPs, RFAs) within 3 days.
>
> **Current workflow (4-6 hours):** Read every file. Take notes on a legal pad. Cross-reference files manually. Open the objection drafter. Manually type facts from memory.
>
> **LITIGAGENT workflow (45 minutes):** Drop the folder. Review extraction (fix any OCR errors in the police report scan). Add notes: "Company and employee have adverse interests. Employee is a permissive driver — within course and scope. No company representative at scene." Click "Prepare Discovery" → objection drafter pre-populated with case context and file references.

#### UC-2: Initial Case Analysis for New Client
> A plaintiff's attorney meets a potential client who was terminated. The client brings: termination letter, performance reviews (3 years), emails with supervisor, employee handbook excerpt, and a photo of a whiteboard with discriminatory comments.
>
> **LITIGAGENT workflow:** Upload all files. OCR extracts text from the whiteboard photo. Attorney adds notes: "Client is 58 years old, Hispanic, 12 years tenure. Replaced by 32-year-old. Client believes age and race discrimination." Chat: "Based on these documents, what potential claims does the client have under California law?" → AI cross-references case files with employment law knowledge base, cites specific documents and statutes.

#### UC-3: Demand Letter Drafting
> Attorney has fully analyzed a wrongful termination case (50 documents ingested, notes captured). Needs to draft a demand letter to opposing counsel.
>
> **LITIGAGENT workflow:** Click "Draft Demand Letter." AI has full context: all documents, attorney notes, applicable statutes (from existing knowledge base), and case law. Generates a demand letter that cites specific documents by name ("As reflected in the March 15, 2025 email from Supervisor Johnson to HR...") and applicable law.

#### UC-4: Settlement Conference Preparation
> Attorney needs to prepare a settlement brief and damages summary for a mandatory settlement conference.
>
> **LITIGAGENT workflow:** Chat: "Summarize all damages evidence across the case files." AI identifies medical bills (from spreadsheet), lost wages (from pay stubs), emotional distress evidence (from therapist notes), and punitive damages basis (from the discriminatory emails). Attorney clicks "Generate Settlement Brief" with the summary as a starting point.

#### UC-5: Associate Handoff
> Senior partner is handing a case to a new associate. 200+ documents, 18 months of history.
>
> **LITIGAGENT workflow:** New associate opens the case. Reads attorney notes first (5 minutes). Chats: "Give me a timeline of key events." "Who are all the parties and their roles?" "What are the strongest documents supporting our case?" Within 30 minutes, the associate has a working understanding of an 18-month case.

### 4.2 User Stories (MVP)

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As an attorney, I want to drag and drop a folder of case files so I can ingest an entire case at once | P0 |
| US-02 | As an attorney, I want to see a list of all uploaded files with their processing status so I can track ingestion progress | P0 |
| US-03 | As an attorney, I want to see the extracted text from all files in a single scrollable view so I can review the case as a continuous document | P0 |
| US-04 | As an attorney, I want to click a file name and jump to its content in the text view so I can navigate quickly | P0 |
| US-05 | As an attorney, I want to edit the extracted text so I can correct OCR errors or redact sensitive information | P0 |
| US-06 | As an attorney, I want to add general case notes so I can capture context the files don't contain | P0 |
| US-07 | As an attorney, I want to add notes linked to a specific file so I can annotate individual documents | P1 |
| US-08 | As an attorney, I want to chat with my case files so I can ask questions and get answers citing specific documents | P0 |
| US-09 | As an attorney, I want the AI to use my notes as context when answering questions so my judgment is reflected | P0 |
| US-10 | As an attorney, I want to search across all extracted text so I can find specific content quickly | P1 |
| US-11 | As an attorney, I want to see OCR confidence indicators so I can identify text that may need manual review | P1 |
| US-12 | As an attorney, I want to create multiple cases so I can manage different matters separately | P0 |
| US-13 | As an attorney, I want my cases to persist across sessions so I can return to them later | P0 |
| US-14 | As an attorney, I want to export the unified text view so I can share it with co-counsel | P2 |
| US-15 | As an attorney, I want to transition from chat to a workflow (e.g., demand letter, discovery) so the AI uses case context | P1 |
| US-16 | As an attorney, I want to filter files by type (PDF, email, spreadsheet) so I can focus on specific document categories | P2 |
| US-17 | As an attorney, I want to re-upload a corrected version of a file so the extracted text updates | P2 |

---

## 5. Architecture & Technical Design

### 5.1 Architectural Principles

Following Clean Architecture and the existing codebase patterns:

1. **The Dependency Rule applies.** Case ingestion domain logic (extraction, chunking, case management) must not depend on FastAPI, LanceDB, or any framework. Dependencies point inward.
2. **Case files are a new Bounded Context.** They share the embedding/retrieval infrastructure with the knowledge base but are conceptually separate. A `CaseFile` is not a `Document` from a statutory source. Different lifecycle, different access patterns, different ownership.
3. **The extraction pipeline is a Strategy pattern.** Each file type (PDF, DOCX, EML, XLSX, etc.) gets an extractor. New formats are added by implementing the interface, not modifying existing code (OCP).
4. **Case data is tenant-isolated.** Even in MVP (single user), design for per-case isolation from day one. Case files never leak across cases. This is non-negotiable for attorney-client privilege.
5. **Editable text is the canonical representation.** After extraction, the attorney's edited version is the source of truth. Original files are retained for re-extraction, but the edited text is what gets embedded and sent to the LLM.

### 5.2 Domain Model

```
CaseBoundedContext
├── Case (Aggregate Root)
│   ├── case_id: UUID
│   ├── name: str
│   ├── created_at: datetime
│   ├── updated_at: datetime
│   └── status: CaseStatus (ACTIVE | ARCHIVED)
│
├── CaseFile (Entity, belongs to Case)
│   ├── file_id: UUID
│   ├── case_id: UUID (FK)
│   ├── original_filename: str
│   ├── file_type: FileType (PDF | DOCX | XLSX | CSV | EML | MSG | TXT | IMAGE | PPTX)
│   ├── file_size_bytes: int
│   ├── mime_type: str
│   ├── storage_path: str (path to original file)
│   ├── upload_order: int (preserves drag-drop ordering)
│   ├── processing_status: ProcessingStatus (QUEUED | PROCESSING | READY | ERROR)
│   ├── error_message: str | None
│   ├── extracted_text: str (raw extraction output)
│   ├── edited_text: str (attorney-edited version — the canonical text)
│   ├── text_dirty: bool (True if edited_text differs from extracted_text)
│   ├── ocr_confidence: float | None (0.0-1.0, only for OCR'd files)
│   ├── page_count: int | None
│   ├── metadata: dict (file-specific: email headers, spreadsheet sheet names, etc.)
│   ├── created_at: datetime
│   └── updated_at: datetime
│
├── CaseNote (Entity, belongs to Case, optionally to CaseFile)
│   ├── note_id: UUID
│   ├── case_id: UUID (FK)
│   ├── file_id: UUID | None (FK, None = general case note)
│   ├── content: str (markdown)
│   ├── created_at: datetime
│   └── updated_at: datetime
│
├── CaseChunk (Entity, belongs to CaseFile)
│   ├── chunk_id: UUID
│   ├── file_id: UUID (FK)
│   ├── case_id: UUID (FK)
│   ├── chunk_index: int
│   ├── content: str
│   ├── heading_path: str (e.g., "police_report.pdf > Page 3")
│   ├── token_count: int
│   ├── content_hash: str
│   └── is_active: bool
│
└── CaseChatSession (Entity, belongs to Case)
    ├── session_id: UUID
    ├── case_id: UUID (FK)
    ├── created_at: datetime
    └── turns: list[CaseChatTurn]
```

### 5.3 Module Structure

```
src/employee_help/
├── casefile/                          # NEW: Case File Bounded Context
│   ├── __init__.py
│   ├── models.py                      # Domain models (Case, CaseFile, CaseNote, CaseChunk)
│   ├── storage.py                     # CaseStorage (SQLite, separate from KnowledgeBase storage)
│   ├── service.py                     # CaseService (orchestrates extraction, chunking, embedding)
│   ├── extractors/                    # File type extractors (Strategy pattern)
│   │   ├── __init__.py
│   │   ├── base.py                    # ExtractorBase (abstract)
│   │   ├── pdf.py                     # PDFExtractor (pdfplumber + OCR fallback)
│   │   ├── docx.py                    # DocxExtractor (python-docx)
│   │   ├── xlsx.py                    # ExcelExtractor (openpyxl)
│   │   ├── csv_ext.py                 # CSVExtractor (stdlib csv)
│   │   ├── email.py                   # EmailExtractor (eml via stdlib, msg via extract-msg)
│   │   ├── image.py                   # ImageExtractor (OCR via pytesseract/ocrmypdf)
│   │   ├── text.py                    # PlainTextExtractor (passthrough with encoding detection)
│   │   ├── pptx.py                    # PowerPointExtractor (python-pptx)
│   │   └── registry.py               # ExtractorRegistry (maps MIME type → Extractor)
│   ├── chunker.py                     # CaseFileChunker (page-aware chunking for case files)
│   └── chat.py                        # CaseChatService (case-scoped RAG with notes context)
│
├── api/
│   ├── casefile_routes.py             # NEW: Case file API endpoints
│   └── casefile_schemas.py            # NEW: Pydantic models for case file API
│
frontend/
├── app/tools/litigagent/
│   ├── page.tsx                       # LITIGAGENT main page
│   └── [caseId]/
│       └── page.tsx                   # Case detail (three-panel view)
├── components/litigagent/
│   ├── file-panel.tsx                 # Panel 1: File list
│   ├── text-panel.tsx                 # Panel 2: Extracted text viewer/editor
│   ├── notes-panel.tsx                # Panel 3: Attorney notes
│   ├── file-drop-zone.tsx             # Drag-and-drop area
│   ├── file-list-item.tsx             # Individual file entry
│   ├── text-section-header.tsx        # Read-only file divider in text panel
│   ├── case-chat.tsx                  # Chat overlay/drawer
│   ├── case-list.tsx                  # Case listing page
│   └── workflow-launcher.tsx          # Workflow entry point buttons
├── lib/
│   ├── casefile-api.ts                # API client
│   └── casefile-context.tsx           # State management
```

### 5.4 Dependency Architecture

```
                    ┌─────────────────────────────┐
                    │         Frontend             │
                    │   (Next.js / React)          │
                    └──────────┬──────────────────-┘
                               │ HTTP/SSE
                    ┌──────────▼──────────────────-┐
                    │      API Layer               │
                    │  (casefile_routes.py)         │
                    │  (casefile_schemas.py)        │
                    └──────────┬──────────────────-┘
                               │ calls
                    ┌──────────▼──────────────────-┐
                    │     Application Layer         │
                    │  (CaseService)                │
                    │  (CaseChatService)            │
                    └─────┬────────────┬───────────┘
                          │            │
              ┌───────────▼──┐   ┌─────▼───────────┐
              │ Domain Layer │   │  Domain Layer    │
              │ (extractors) │   │  (models)        │
              │ (chunker)    │   │  (Case, CaseFile │
              │ (registry)   │   │   CaseNote, etc) │
              └───────────┬──┘   └─────┬───────────┘
                          │            │
              ┌───────────▼────────────▼───────────┐
              │     Infrastructure Layer            │
              │  (CaseStorage - SQLite)             │
              │  (FileStorage - local disk)         │
              │  (EmbeddingService - shared)        │
              │  (VectorStore - separate table)     │
              │  (LLMClient - shared)               │
              └────────────────────────────────────┘
```

**Key boundary decisions:**

1. **Separate SQLite tables, same database file.** Case data lives in new tables (`cases`, `case_files`, `case_notes`, `case_chunks`) in the same `employee_help.db`. This shares the WAL mode benefits and avoids managing a second database.

2. **Separate LanceDB table.** Case file embeddings go in `case_embeddings` (not `chunk_embeddings`). This prevents case files from polluting knowledge base search results, and enables case-scoped vector search.

3. **Shared embedding service.** Same `bge-base-en-v1.5` model, same `EmbeddingService` class. No reason to load a second model.

4. **Shared LLM client.** Same `LLMClient` (Anthropic API), different prompt templates. Case chat uses `config/prompts/casefile_system.j2`.

5. **File storage is local disk.** Original files stored under `data/cases/{case_id}/files/{file_id}/{original_filename}`. Not in SQLite (BLOBs are an anti-pattern for files >1MB).

### 5.5 Extractor Interface (Strategy Pattern)

```python
# src/employee_help/casefile/extractors/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    """Result of extracting text from a file."""
    text: str                          # Extracted plain text / markdown
    page_count: int | None             # Number of pages (if applicable)
    ocr_confidence: float | None       # 0.0-1.0 (None if no OCR used)
    metadata: dict                     # Format-specific metadata
    warnings: list[str]                # Non-fatal extraction issues

class FileExtractor(ABC):
    """Base interface for all file type extractors."""

    @abstractmethod
    def can_extract(self, mime_type: str, extension: str) -> bool:
        """Return True if this extractor handles the given file type."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract text content from the given file bytes."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this extractor supports."""
```

**Extractor implementations:**

| Extractor | Extensions | Library | Notes |
|-----------|-----------|---------|-------|
| `PDFExtractor` | `.pdf` | pdfplumber (text) + pytesseract (OCR fallback) | Detects scanned pages via text density. Falls back to OCR per-page. Reports OCR confidence. |
| `DocxExtractor` | `.docx` | python-docx | Extracts paragraphs, tables, headers/footers. Preserves heading structure. |
| `ExcelExtractor` | `.xlsx`, `.xls` | openpyxl | Extracts each sheet as a markdown table. Sheet names as headings. |
| `CSVExtractor` | `.csv`, `.tsv` | stdlib csv | Renders as markdown table. Auto-detects delimiter. |
| `EmailExtractor` | `.eml`, `.msg` | stdlib email.parser (EML) + extract-msg (MSG) | Extracts headers (From, To, Date, Subject) + body. Recursively extracts attachments. |
| `ImageExtractor` | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | pytesseract + Pillow | Pure OCR. Reports confidence. Preprocessing: deskew, denoise. |
| `PlainTextExtractor` | `.txt`, `.md`, `.rtf` | stdlib + chardet | Encoding detection. Passthrough for .txt/.md. |
| `PowerPointExtractor` | `.pptx` | python-pptx | Extracts slide text, speaker notes. Slide numbers as headings. |

**ExtractorRegistry** resolves MIME type + extension → extractor instance. New formats are added by implementing `FileExtractor` and registering — zero changes to existing code (OCP).

### 5.6 Chunking Strategy for Case Files

Case files are heterogeneous and need a different chunking strategy than the knowledge base:

```python
def chunk_case_file(
    edited_text: str,
    filename: str,
    file_type: FileType,
    max_tokens: int = 1000,       # Smaller chunks for case files (more precise retrieval)
    overlap_tokens: int = 100,
) -> list[CaseChunkResult]:
```

**Key differences from knowledge base chunking:**

| Aspect | Knowledge Base | Case Files |
|--------|---------------|------------|
| **Chunk size** | 1500 tokens (statutory sections are long) | 1000 tokens (case file text is varied, precision matters) |
| **Strategy** | Section boundary / heading based | Page-aware + paragraph boundary |
| **Heading path** | `"Labor Code > Division 2 > Part 1 > § 1102.5"` | `"police_report.pdf > Page 3"` |
| **Identity** | Content hash (dedup across sources) | File ID + chunk index (no dedup — same text in different files is meaningful) |
| **Overlap** | 100 tokens | 100 tokens (same) |

**Page-aware chunking:**
- For PDFs: chunk at page boundaries when possible, sub-chunk pages that exceed max_tokens
- For emails: chunk at thread/message boundaries
- For spreadsheets: chunk per sheet (most sheets fit in one chunk)
- For all types: respect paragraph boundaries as secondary split points

---

## 6. UI/UX Design

### 6.1 Design Philosophy

**Target user:** A busy litigation attorney who needs to work fast and trust the tool. They are **not** exploring — they have a stack of files and a deadline.

**Core UX principles for LITIGAGENT:**

1. **Zero learning curve.** If you can use Finder/Explorer and a text editor, you can use LITIGAGENT. No tutorials needed.
2. **Trust through transparency.** Show the raw extraction. Let them edit it. Show OCR confidence. Never hide what the AI sees.
3. **Speed over features.** A file should go from drag to readable text in under 5 seconds. 100 files in under 2 minutes.
4. **Progressive disclosure.** Three panels is already complex. Chat and workflows appear only when the attorney is ready (drawer/overlay pattern, not visible by default).
5. **Desktop-first.** Attorneys doing case analysis are at their desk with a wide monitor. Design for 1440px+ first. Provide a usable (not equivalent) mobile experience for reviewing on-the-go.

### 6.2 Layout Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  LITIGAGENT    │  Case: Johnson v. Acme Corp          │  💬 Chat   │
│  [← Cases]     │  87 files · 342 pages · Ready        │  [⚡ Actions]│
├────────────────┼──────────────────────────────────────-┼────────────┤
│                │                                       │            │
│  FILES         │  EXTRACTED TEXT                        │  NOTES     │
│  ─────         │  ──────────────                       │  ─────     │
│                │                                       │            │
│  🔍 Search     │  ┌─────────────────────────────────┐  │  📝 Case   │
│  ─────────     │  │ ═══ police_report.pdf ═══       │  │  Notes     │
│                │  │ [PDF · 12 pages · ⚠ OCR 0.87]   │  │  ──────   │
│  📁 All Files  │  │                                  │  │           │
│    ├ 📄 police │  │  On March 15, 2025, at approx.  │  │  Company  │
│    │   _report │  │  2:30 PM, the reporting officer  │  │  and the  │
│    │   .pdf ✅  │  │  responded to a traffic          │  │  employee  │
│    ├ 📄 medica │  │  collision at the intersection   │  │  have     │
│    │   l_recor │  │  of Main St and 5th Ave...       │  │  adverse  │
│    │   ds.pdf  │  │                                  │  │  inter-   │
│    │   ✅       │  │  [editable text continues...]    │  │  ests.    │
│    ├ 📧 superv │  │                                  │  │           │
│    │   isor_em │  │  ═══ medical_records.pdf ═══     │  │  ──────   │
│    │   ail.eml │  │  [PDF · 45 pages · Text OK]      │  │           │
│    │   ✅       │  │                                  │  │  📎 Note  │
│    ├ 📊 payrol │  │  Patient: Jane Johnson           │  │  for:     │
│    │   l.xlsx  │  │  DOB: 04/12/1985                 │  │  police   │
│    │   ✅       │  │  Date of Visit: 03/15/2025       │  │  _report  │
│    ├ 📄 employ │  │  ...                             │  │  .pdf     │
│    │   ee_hand │  │                                  │  │  ──────   │
│    │   book    │  │                                  │  │  "Page 4  │
│    │   .pdf 🔄  │  │                                  │  │  has the  │
│    └ ...       │  │                                  │  │  key      │
│                │  │                                  │  │  quote"   │
│  ─────────     │  └─────────────────────────────────┘  │           │
│  + Upload      │                                       │  + Add     │
│    more files  │  [Search extracted text... 🔍]        │    Note    │
│                │                                       │            │
├────────────────┼──────────────────────────────────────-┼────────────┤
│  Filter ▾      │  Showing 87 of 87 files               │            │
│  Sort ▾        │  ████████████████████ 100% processed  │            │
└────────────────┴──────────────────────────────────────-┴────────────┘
```

### 6.3 Panel Specifications

#### Panel 1: File Panel (Left) — 280px fixed width

**Drag-and-drop zone:**
- Full-panel drop zone (visible on drag-over with dashed border + "Drop files here" message)
- Accepts individual files AND folders (recursive extraction)
- Supports click-to-browse as fallback
- Maximum file size: 50MB per file, 500MB per case (MVP)

**File list:**
- Each file shows: icon (by type), truncated filename (tooltip for full), status indicator
- Status indicators:
  - `🔄` Spinning = Processing
  - `✅` Green check = Ready
  - `⚠️` Yellow warning = Ready with OCR quality issues (confidence < 0.85)
  - `❌` Red X = Error (click to see error message)
- Click file → Panel 2 smooth-scrolls to that file's header
- Right-click context menu: Re-process, Delete, Download original, View details
- Drag to reorder (changes order in Panel 2)

**Filtering & search (collapsed by default, expands on click):**
- Filter by file type: PDF, Email, Spreadsheet, Word, Image, Other
- Filter by status: All, Ready, Processing, Errors
- Sort: Upload order (default), Alphabetical, File size, Page count
- Search: filters file list by filename substring

**Handling 100+ files:**
- Virtualized list (react-window or similar) for performance
- Folder grouping: if files were uploaded from folders, preserve and display folder structure
- Collapse/expand folders
- File count badge: "87 files (3 processing)"

#### Panel 2: Text Panel (Center) — Fluid width (fills remaining space)

**File section headers (read-only):**
```
═══════════════════════════════════════════════
📄 police_report.pdf
PDF · 12 pages · OCR confidence: 87% ⚠️
═══════════════════════════════════════════════
```
- Sticky header when scrolling within a file's content (shows current file context)
- Visual anchor IDs for Panel 1 click-to-navigate
- Not editable (clearly visually distinct: background color, border)

**Extracted text (editable):**
- `contenteditable` or controlled textarea sections between headers
- Preserves markdown formatting (headings, tables, lists) from extraction
- Changes save automatically (debounced, 500ms after last keystroke)
- Change indicator: subtle highlight on sections that differ from original extraction
- "Reset to original" button per file section (revert edits)

**Performance for large content:**
- **Virtualized rendering.** Do NOT render all 100 files' text at once. Use intersection observer to render only visible sections + 2 sections above/below.
- Estimated total content: 100 files × ~10 pages × ~500 words = 500K words = ~2.5M characters. Must virtualize.
- Each file section is a lazy-loaded component. Scroll position triggers load.

**Search bar (bottom of panel):**
- Ctrl+F / Cmd+F intercept for in-panel search
- Highlights matches across all loaded sections
- Shows match count and navigation arrows (prev/next)

**OCR confidence visualization:**
- For OCR'd text, subtle background tint on low-confidence passages (< 0.7)
- Tooltip: "This text was extracted via OCR. Confidence: 72%. Please verify."

#### Panel 3: Notes Panel (Right) — 320px fixed width, collapsible

**Two note types:**

1. **Case Notes** (general, not linked to a file):
   - Free-form markdown editor
   - Collapsible sections
   - Example: "Theory of case: Age discrimination under FEHA. Client replaced by significantly younger employee."

2. **File Notes** (linked to a specific file):
   - Shows the linked file name as a chip/badge at the top
   - Created by: clicking "+ Add Note" with a file selected in Panel 1, or right-clicking a file → "Add Note"
   - When scrolling Panel 2, if current file has notes, subtle indicator appears in Panel 3

**Notes structure:**
- Reverse chronological (newest first)
- Each note shows: timestamp, linked file (if any), content
- Inline editing (click to edit, blur to save)
- Delete with confirmation

**Collapse behavior:**
- Panel 3 collapses to a narrow strip (40px) with a "Notes (4)" badge
- Click to expand. Useful when attorney wants maximum text panel width.

### 6.4 Chat Overlay

**Not a panel — a drawer.** Chat slides in from the right (over Panel 3, or as a bottom sheet on mobile) when the attorney clicks the "Chat" button in the header.

```
┌────────────────────────────────────────────┐
│  💬 Chat with Case                    [✕]  │
│  ─────────────────────────────────────     │
│                                            │
│  You: What did the police report say       │
│  about the driver's statement?             │
│                                            │
│  AI: According to police_report.pdf        │
│  (page 4), the driver stated that          │
│  "I was making a left turn and didn't      │
│  see the oncoming vehicle." The report     │
│  also notes that the driver was within     │
│  the scope of employment at the time       │
│  of the incident.                          │
│  📎 police_report.pdf, p.4                 │
│  📎 employment_verification.docx           │
│                                            │
│  You: Based on these files and my notes,   │
│  what are the strongest claims?            │
│                                            │
│  AI: Based on the case files and your      │
│  notes about adverse interests, I          │
│  identify the following claims...          │
│  ...                                       │
│                                            │
├────────────────────────────────────────────┤
│  [Ask about this case...              ] ⏎  │
│                                            │
│  Suggested:                                │
│  · Summarize all damages evidence          │
│  · Create a timeline of key events         │
│  · What witnesses are identified?          │
└────────────────────────────────────────────┘
```

**Chat behavior:**
- AI context = all case file chunks + all notes + knowledge base (employment law)
- File citations in responses are clickable → Panel 2 scrolls to the cited location
- Suggested questions are contextual (generated from file analysis)
- Conversation history persists per case

### 6.5 Workflow Launcher

The "Actions" button in the header opens a dropdown:

```
⚡ Actions
├── 📝 Draft Demand Letter
├── 📋 Prepare Discovery (→ Objection Drafter with case context)
├── 📊 Generate Case Analysis
├── ⏱️ Build Timeline
├── 📑 Prepare Settlement Brief
└── 📤 Export All Text
```

Each workflow:
1. Opens in a new view (not overlay — full page)
2. Pre-loads all case context (files, notes, chat history)
3. Uses the existing Employee Help knowledge base for legal research
4. Returns to LITIGAGENT three-panel view on completion

### 6.6 Responsive Design

| Breakpoint | Layout |
|-----------|--------|
| **≥1440px** | Three panels visible. Chat as right drawer. |
| **1024-1439px** | Two panels (Files + Text). Notes as collapsible right drawer. |
| **768-1023px** | Single panel with tab bar (Files / Text / Notes). Chat as bottom sheet. |
| **<768px** | Single panel. Simplified file list. Read-only text view (no editing). Chat as full-screen overlay. |

**Mobile is view-only for MVP.** Editing extracted text on mobile is poor UX. Allow browsing, reading, note-taking, and chatting. Reserve editing for desktop.

### 6.7 Color & Typography

**Consistent with existing Employee Help design.** Extend the current Tailwind config:

- File panel background: `bg-gray-50` (light) / `bg-gray-900` (dark)
- Text panel background: `bg-white` (light) / `bg-gray-800` (dark)
- Notes panel background: `bg-amber-50/50` (light, warm tint for "personal notes" feel) / `bg-amber-900/20` (dark)
- File section headers: `bg-blue-50 border-blue-200` (light)
- OCR warning tint: `bg-yellow-50`
- Status colors: green-500 (ready), yellow-500 (warning), red-500 (error), blue-500 (processing)

**Typography:**
- File names in Panel 1: `text-sm font-medium truncate`
- Section headers in Panel 2: `text-base font-semibold` with file type icon
- Extracted text: `text-sm leading-relaxed font-mono` (monospace for editability and scan-readability)
- Notes: `text-sm leading-relaxed` (proportional, warmer feel)

### 6.8 Accessibility

- All panels keyboard-navigable. Tab order: Files → Text → Notes.
- File list items are `role="listbox"` with `aria-selected`.
- Text panel sections use `role="region"` with `aria-label="Content from {filename}"`.
- Status indicators use `aria-label` (not just color/emoji).
- Drag-and-drop has keyboard alternative (Tab to drop zone, Enter to open file picker).
- 44px minimum touch targets for all interactive elements.
- Panel resize handles are keyboard-accessible (arrow keys).
- Screen reader announces: "File uploaded. Processing. Ready." state transitions.

---

## 7. Data Model & Storage Schema

### 7.1 SQLite Tables (new tables in existing `employee_help.db`)

```sql
-- Case table (aggregate root)
CREATE TABLE cases (
    id TEXT PRIMARY KEY,                    -- UUID
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',  -- active | archived
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Case files table
CREATE TABLE case_files (
    id TEXT PRIMARY KEY,                     -- UUID
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,                 -- pdf | docx | xlsx | csv | eml | msg | txt | image | pptx
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,              -- relative path under data/cases/
    upload_order INTEGER NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'queued',  -- queued | processing | ready | error
    error_message TEXT,
    extracted_text TEXT,                     -- raw extraction output
    edited_text TEXT,                        -- attorney-edited (canonical for embedding)
    text_dirty INTEGER NOT NULL DEFAULT 0,  -- 1 if edited_text differs from extracted_text
    ocr_confidence REAL,                    -- 0.0-1.0 (NULL if no OCR)
    page_count INTEGER,
    metadata TEXT,                           -- JSON (email headers, sheet names, etc.)
    content_hash TEXT,                       -- SHA-256 of edited_text (for change detection)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_case_files_case_id ON case_files(case_id);
CREATE INDEX idx_case_files_status ON case_files(processing_status);

-- Case notes table
CREATE TABLE case_notes (
    id TEXT PRIMARY KEY,                     -- UUID
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    file_id TEXT REFERENCES case_files(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_case_notes_case_id ON case_notes(case_id);
CREATE INDEX idx_case_notes_file_id ON case_notes(file_id);

-- Case chunks table (for embedding/retrieval)
CREATE TABLE case_chunks (
    id TEXT PRIMARY KEY,                     -- UUID
    file_id TEXT NOT NULL REFERENCES case_files(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    heading_path TEXT NOT NULL,              -- "filename.pdf > Page 3"
    token_count INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_case_chunks_case_id ON case_chunks(case_id);
CREATE INDEX idx_case_chunks_file_id ON case_chunks(file_id);
CREATE INDEX idx_case_chunks_hash ON case_chunks(content_hash);

-- Case chat sessions
CREATE TABLE case_chat_sessions (
    id TEXT PRIMARY KEY,                     -- UUID
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Case chat turns
CREATE TABLE case_chat_turns (
    id TEXT PRIMARY KEY,                     -- UUID
    session_id TEXT NOT NULL REFERENCES case_chat_sessions(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    role TEXT NOT NULL,                      -- user | assistant
    content TEXT NOT NULL,
    sources TEXT,                            -- JSON array of cited file references
    created_at TEXT NOT NULL
);
CREATE INDEX idx_case_chat_turns_session ON case_chat_turns(session_id);
```

### 7.2 LanceDB Table (case file embeddings)

Separate table `case_embeddings` in the same LanceDB directory:

```python
# Schema matches existing chunk_embeddings but with case-specific fields
case_embedding_schema = {
    "chunk_id": str,           # UUID string
    "file_id": str,            # UUID string
    "case_id": str,            # UUID string
    "content": str,            # Chunk text (for FTS)
    "heading_path": str,       # "filename.pdf > Page 3"
    "dense_vector": list[float],  # 768-dim bge-base-en-v1.5
    "content_hash": str,
    "is_active": int,          # 1 or 0
    "file_type": str,          # pdf, docx, etc.
    "original_filename": str,  # For display in results
}
```

**Case-scoped search:** All vector/hybrid searches filter by `case_id` to ensure isolation.

### 7.3 File Storage Layout

```
data/
├── cases/
│   ├── {case_id}/
│   │   ├── files/
│   │   │   ├── {file_id}_{original_filename}
│   │   │   └── ...
│   │   └── exports/              # Generated work product
│   │       ├── demand_letter_2026-03-06.docx
│   │       └── ...
│   └── ...
├── lancedb/
│   ├── chunk_embeddings/          # Existing knowledge base
│   └── case_embeddings/           # NEW: case file embeddings
└── ...
```

---

## 8. File Processing Pipeline

### 8.1 Upload Flow

```
User drops files
       │
       ▼
  Frontend validates
  (extension, size)
       │
       ▼
  POST /api/cases/{id}/files
  (multipart/form-data)
       │
       ▼
  API saves to disk
  Creates case_files row
  (status: QUEUED)
       │
       ▼
  Returns immediately
  (file_id, status: queued)
       │
       ▼
  Background task:
  ┌─────────────────────────┐
  │ 1. Resolve extractor    │
  │    (ExtractorRegistry)  │
  │                         │
  │ 2. Extract text         │
  │    (Strategy pattern)   │
  │                         │
  │ 3. Store extracted_text │
  │    + edited_text        │
  │    (status: READY)      │
  │                         │
  │ 4. Chunk edited_text    │
  │    (CaseFileChunker)    │
  │                         │
  │ 5. Embed chunks         │
  │    (EmbeddingService)   │
  │                         │
  │ 6. Upsert to LanceDB   │
  │    (case_embeddings)    │
  └─────────────────────────┘
       │
       ▼
  SSE event: file_ready
  (sent to frontend)
```

### 8.2 Background Processing

**Why background?** OCR can take 2-5 seconds per page. A 50-page scanned PDF = ~100-250 seconds. The upload must return instantly.

**Implementation:** Use `asyncio.create_task()` for processing (same process, no external task queue needed for MVP). Scale to Celery/Redis if processing volume demands it later.

**SSE status stream:** A dedicated SSE endpoint (`GET /api/cases/{id}/status-stream`) pushes file status updates to the frontend in real-time:

```
event: file_status
data: {"file_id": "abc", "status": "processing", "progress": 0.4}

event: file_status
data: {"file_id": "abc", "status": "ready", "ocr_confidence": 0.87}

event: file_status
data: {"file_id": "def", "status": "error", "message": "Password-protected PDF"}
```

### 8.3 Re-Embedding on Edit

When the attorney edits text in Panel 2:
1. `PATCH /api/cases/{case_id}/files/{file_id}` with `{ edited_text: "..." }`
2. Backend marks `text_dirty = True`, updates `content_hash`
3. Background task: re-chunks `edited_text`, re-embeds, upserts to LanceDB
4. Debounced: re-embedding triggers only after 5 seconds of no edits (not on every keystroke)

### 8.4 Supported File Types (MVP)

| Format | Extensions | Library | OCR Needed | Priority |
|--------|-----------|---------|-----------|----------|
| PDF (text) | `.pdf` | pdfplumber | No | P0 |
| PDF (scanned) | `.pdf` | pdfplumber + pytesseract | Yes | P0 |
| Word | `.docx` | python-docx | No | P0 |
| Email (EML) | `.eml` | stdlib email.parser | No | P0 |
| Email (MSG) | `.msg` | extract-msg | No | P0 |
| Excel | `.xlsx` | openpyxl | No | P1 |
| CSV/TSV | `.csv`, `.tsv` | stdlib csv | No | P1 |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff` | pytesseract + Pillow | Yes | P1 |
| Plain text | `.txt`, `.md` | stdlib | No | P0 |
| PowerPoint | `.pptx` | python-pptx | No | P2 |

**Not supported in MVP:** `.doc` (legacy Word), `.xls` (legacy Excel), `.rtf`, video, audio, `.zip` (auto-extract). These are Phase 2 candidates.

### 8.5 Email Attachment Handling

When an `.eml` or `.msg` file contains attachments:
1. Email body is extracted as a text section
2. Each attachment is extracted as a separate `CaseFile` entry
3. The attachment's `metadata` includes `{"parent_email_id": "...", "attached_to": "supervisor_email.eml"}`
4. In Panel 1, attachments indent under their parent email
5. In Panel 2, attachments appear immediately after the email body section

### 8.6 New Dependencies

| Library | Purpose | Size | Already in deps? |
|---------|---------|------|-----------------|
| pdfplumber | PDF text extraction | Light | YES |
| python-docx | DOCX extraction | Light | YES (via docxtpl) |
| openpyxl | Excel extraction | Medium | NO (new) |
| pytesseract | OCR engine wrapper | Light | NO (new) |
| Pillow | Image preprocessing | Medium | NO (new) |
| extract-msg | MSG email parsing | Light | NO (new) |
| chardet | Encoding detection | Light | NO (new) |
| python-pptx | PowerPoint extraction | Light | NO (new, P2) |

**System dependency:** Tesseract OCR engine must be installed (`brew install tesseract` on macOS, `apt-get install tesseract-ocr` on Linux). Documented in setup instructions.

**Dependency isolation (ISP):** All new dependencies go in a `[casefile]` optional group in `pyproject.toml`. Users who don't need LITIGAGENT don't pay for these dependencies.

---

## 9. API Design

### 9.1 Case Management

```
POST   /api/cases                              Create a new case
GET    /api/cases                              List all cases
GET    /api/cases/{case_id}                    Get case details
PATCH  /api/cases/{case_id}                    Update case (name, description)
DELETE /api/cases/{case_id}                    Archive case (soft delete)
```

### 9.2 File Management

```
POST   /api/cases/{case_id}/files              Upload files (multipart, batch)
GET    /api/cases/{case_id}/files              List files in case
GET    /api/cases/{case_id}/files/{file_id}    Get file details + extracted text
PATCH  /api/cases/{case_id}/files/{file_id}    Update edited text
DELETE /api/cases/{case_id}/files/{file_id}    Remove file from case
POST   /api/cases/{case_id}/files/{file_id}/reprocess  Re-extract text
GET    /api/cases/{case_id}/files/{file_id}/download    Download original file
GET    /api/cases/{case_id}/status-stream      SSE: file processing status updates
```

### 9.3 Notes

```
POST   /api/cases/{case_id}/notes              Create a note
GET    /api/cases/{case_id}/notes              List notes (optionally filter by file_id)
PATCH  /api/cases/{case_id}/notes/{note_id}    Update note
DELETE /api/cases/{case_id}/notes/{note_id}    Delete note
```

### 9.4 Case Chat

```
POST   /api/cases/{case_id}/chat               Ask a question (SSE streaming response)
GET    /api/cases/{case_id}/chat/sessions       List chat sessions
GET    /api/cases/{case_id}/chat/{session_id}   Get chat history
```

### 9.5 Composite Text View

```
GET    /api/cases/{case_id}/composite-text     Get full composite text (all files, ordered)
```

Returns:
```json
{
  "case_id": "...",
  "sections": [
    {
      "file_id": "abc",
      "filename": "police_report.pdf",
      "file_type": "pdf",
      "page_count": 12,
      "ocr_confidence": 0.87,
      "status": "ready",
      "edited_text": "On March 15, 2025...",
      "text_dirty": false,
      "notes": [
        {"note_id": "n1", "content": "Key quote on page 4"}
      ]
    },
    ...
  ],
  "total_files": 87,
  "total_pages": 342,
  "processing_complete": true
}
```

### 9.6 Workflow Launch

```
POST   /api/cases/{case_id}/workflows/demand-letter      Generate demand letter
POST   /api/cases/{case_id}/workflows/case-analysis       Generate case analysis
POST   /api/cases/{case_id}/workflows/timeline            Generate timeline
```

Each workflow endpoint:
- Receives: optional instructions, selected file IDs (or all)
- Returns: SSE streaming response (same pattern as `/api/ask`)
- Context: case chunks + notes + knowledge base retrieval

### 9.7 Rate Limiting

| Endpoint | Limit |
|----------|-------|
| File upload | 20 files/minute per case |
| Chat | 10 questions/minute per case |
| Workflow | 3 workflows/minute per case |
| Status stream | 1 connection per case |

---

## 10. Retrieval & Chat Integration

### 10.1 Dual-Context Retrieval

Case chat queries search **two** vector stores simultaneously:

1. **Case embeddings** (LanceDB `case_embeddings` table): The attorney's uploaded files, filtered by `case_id`. These are the primary source for case-specific questions.

2. **Knowledge base embeddings** (LanceDB `chunk_embeddings` table): Existing employment law statutes, agency guidance, CACI instructions, case law. These provide the legal research layer.

```python
class CaseChatService:
    def retrieve_for_case(
        self,
        query: str,
        case_id: str,
        mode: str = "attorney",  # Always attorney mode for LITIGAGENT
    ) -> tuple[list[CaseRetrievalResult], list[RetrievalResult]]:
        """
        Returns two result lists:
        1. Case file results (from uploaded documents)
        2. Knowledge base results (from employment law KB)
        """
        # 1. Search case embeddings (case-scoped)
        case_results = self.case_vector_store.search_hybrid(
            query_text=query,
            query_vector=self.embedder.embed_query(query).dense_vector,
            filter_expr=f"case_id = '{case_id}' AND is_active = 1",
            top_k=10,
        )

        # 2. Search knowledge base (existing retrieval service)
        kb_results = self.retrieval_service.retrieve(
            query=query,
            mode=mode,
            top_k=5,
        )

        return case_results, kb_results
```

### 10.2 Prompt Construction

The case chat prompt includes three context layers:

```jinja2
{# config/prompts/casefile_system.j2 #}
You are LITIGAGENT, an AI legal associate reviewing case files for a California litigation attorney.

## Your Knowledge
You have access to two types of sources:
1. **Case Files**: Documents uploaded by the attorney for this specific case.
2. **Legal Research**: California employment law statutes, regulations, agency guidance, CACI jury instructions, and case law.

## Attorney Notes
The attorney has provided the following context and annotations:
{% for note in case_notes %}
{% if note.file_id %}[Note for: {{ note.filename }}]{% else %}[General Case Note]{% endif %}
{{ note.content }}
{% endfor %}

## Instructions
- When citing case files, reference the specific document name and page/section.
- When citing legal authority, provide full statutory citations.
- Distinguish clearly between what the case files say (facts) and what the law says (legal analysis).
- The attorney's notes represent their professional judgment — incorporate them into your analysis.
- If asked to draft work product, use the case files as factual foundation and the legal research for legal authority.
```

### 10.3 Citation Linking

When the AI cites a case file in its response:
- The citation is linked to a specific `file_id` and heading_path (e.g., "police_report.pdf, Page 4")
- The frontend renders these as clickable links
- Clicking scrolls Panel 2 to the exact location
- Citation format: `📎 [filename] p.[page]` or `📎 [filename] § [section]`

---

## 11. Workflow Integration Points

### 11.1 Existing Tools Enhanced by LITIGAGENT

| Existing Tool | Integration | How Case Context Helps |
|--------------|-------------|----------------------|
| **Objection Drafter** (Phase O.1) | "Prepare Discovery" workflow button | Pre-populates case info, party roles, and relevant facts from case files. Attorney doesn't re-enter case details. |
| **Guided Intake** (Phase 4E.4) | Case files provide automatic intake context | Instead of attorney answering intake questions manually, AI extracts answers from case files. |
| **Rights Summary** (Phase 4E.5) | Generate rights summary from case context | Summary is grounded in actual case facts, not hypotheticals. |
| **Demand Letter** (new workflow) | "Draft Demand Letter" workflow button | AI drafts letter citing specific documents ("As evidenced by the March 15 email...") and applicable statutes. |
| **Case Analysis** (new workflow) | "Generate Case Analysis" workflow button | Structured analysis: claims, elements, evidence mapping, strengths/weaknesses. |
| **Timeline** (new workflow) | "Build Timeline" workflow button | AI extracts dates/events from all files, generates chronological timeline. |

### 11.2 Integration Architecture (Anti-Corruption Layer)

Workflows consume case context through a **CaseContext** value object — never by directly accessing case storage:

```python
@dataclass
class CaseContext:
    """Immutable snapshot of case state for workflow consumption."""
    case_id: str
    case_name: str
    files: list[CaseFileSummary]       # filename, type, page_count, edited_text excerpt
    notes: list[CaseNoteSummary]       # content, linked_filename
    chat_history: list[ChatTurn]       # Recent chat turns for continuity
    total_token_count: int             # For budget estimation

    def to_prompt_context(self) -> str:
        """Serialize to a string suitable for LLM context."""

    def get_file_chunks(self, file_ids: list[str] | None = None) -> list[str]:
        """Get chunk contents, optionally filtered to specific files."""
```

This ACL means:
- Workflows don't know about SQLite tables or LanceDB
- Case storage schema can change without breaking workflows
- Workflows are testable with mock `CaseContext` objects
- Context budget is managed in one place (truncation, summarization)

### 11.3 Context Budget Management

With 100 files, total text could be 500K+ words (2M+ tokens). This doesn't fit in any LLM context window.

**Strategy: Retrieval-first, not dump-everything.**

1. **Chat questions:** Retrieve top-10 case chunks + top-5 KB chunks + all notes. Fits in ~8K tokens of context.
2. **Workflows:** Retrieve top-20 case chunks relevant to the workflow type + notes + applicable statutes. ~12K tokens.
3. **Full-case summary (special):** Uses map-reduce summarization. Summarize each file independently, then summarize the summaries. Expensive but cached.
4. **Notes always included in full.** Attorney notes are human-authored, high-signal, and typically short. Always include all notes in context.

---

## 12. Security & Privilege

### 12.1 Attorney-Client Privilege Considerations

**Critical legal context:** A February 2026 court ruling (*U.S. v. Heppner*) held that AI-generated documents lack attorney-client privilege protection when created using consumer AI tools. This makes LITIGAGENT's security posture a **competitive advantage**.

**Privilege-protective features:**
1. **Data isolation:** Case files are never mixed across cases or users.
2. **No training on user data.** Case files are NEVER used for model training. Explicit policy, documented in TOS.
3. **LLM API data handling:** Anthropic's API does not retain or train on data. Documented in their data policy. This is a key trust signal for attorneys.
4. **Encryption at rest:** Case files and extracted text encrypted with AES-256 on disk. (Phase 2 enhancement for production.)
5. **Session-based access:** No persistent user accounts in MVP (local-first). Production: per-user authentication with case-level ACLs.
6. **Audit trail:** All file uploads, edits, chat queries, and workflow generations are logged with timestamps. Supports privilege log documentation.
7. **On-premise option (future):** For firms requiring zero cloud exposure, support fully local deployment (local LLM via Ollama/llama.cpp as an option).

### 12.2 Data Handling Policy

| Data | Storage | Retention | Shared? |
|------|---------|-----------|---------|
| Original files | Local disk (encrypted at rest in production) | Until case archived + 90 days | Never |
| Extracted text | SQLite | Until case archived + 90 days | Never |
| Embeddings | LanceDB | Until case archived + 90 days | Never |
| Attorney notes | SQLite | Until case archived + 90 days | Never |
| Chat history | SQLite | Until case archived + 90 days | Never |
| LLM API calls | Anthropic API (not retained by Anthropic) | Transient | Anthropic processes, doesn't store |

### 12.3 Input Validation & Sanitization

- File size limit: 50MB per file (prevent DoS)
- Case file limit: 500 files per case (prevent resource exhaustion)
- File type allowlist: only supported extensions (prevent malicious files)
- Filename sanitization: strip path traversal characters, limit length
- Text content: sanitize before display (prevent XSS if rendering HTML)
- Magic byte validation: verify file content matches declared MIME type (prevent extension spoofing)

---

## 13. Phasing & MVP Strategy

### 13.1 Lean Startup Approach

**The riskiest assumption:** Attorneys will trust an AI tool with privileged case files AND find the three-panel ingestion UX faster than their current workflow.

**Cheapest experiment to validate:** Build the ingestion MVP (Phases L1-L2) and test with 5 attorneys. Measure: time-to-first-question, OCR correction rate, return rate.

### 13.2 Phase Plan

#### Phase L1: Foundation (Target: 1-2 weeks)
> **Goal:** File upload, extraction, and display. The core ingestion loop.

| Task | Description | Priority |
|------|------------|----------|
| L1.1 | Domain models + SQLite schema (cases, case_files, case_notes, case_chunks) | P0 DONE |
| L1.2 | CaseStorage class (CRUD for all case entities) | P0 DONE |
| L1.3 | ExtractorBase interface + ExtractorRegistry | P0 DONE |
| L1.4 | PDFExtractor (text + OCR fallback) | P0 DONE |
| L1.5 | DocxExtractor | P0 DONE |
| L1.6 | PlainTextExtractor | P0 DONE |
| L1.7 | EmailExtractor (EML + MSG + MBOX) | P0 DONE |
| L1.8 | API routes: case CRUD, file upload, file status SSE | P0 DONE |
| L1.9 | Frontend: case list page, three-panel layout shell | P0 DONE |
| L1.10 | Frontend: drag-and-drop file upload + file list (Panel 1) | P0 DONE |
| L1.11 | Frontend: extracted text display with file headers (Panel 2, read-only) | P0 DONE |
| L1.12 | Tests: extractors (unit), API (integration), frontend (e2e) | P0 DONE |

**Gate L1:** Can upload 10 files (PDF, DOCX, EML, TXT), see extracted text, and navigate between files.

#### Phase L2: Edit + Notes + Polish (Target: 1-2 weeks)
> **Goal:** Make the text editable, add notes, and polish the three-panel UX.

| Task | Description | Priority |
|------|------------|----------|
| L2.1 | Frontend: editable text panel (Panel 2) with debounced save | P0 |
| L2.2 | API: PATCH file edited_text endpoint | P0 |
| L2.3 | Frontend: notes panel (Panel 3) with case notes + file-specific notes | P0 |
| L2.4 | API: notes CRUD endpoints | P0 |
| L2.5 | Frontend: click-to-navigate (Panel 1 → Panel 2) with smooth scroll | P0 |
| L2.6 | ExcelExtractor (XLSX/CSV as markdown tables) | P1 |
| L2.7 | ImageExtractor (OCR with confidence reporting) | P1 |
| L2.8 | OCR confidence indicators in Panel 2 | P1 |
| L2.9 | Frontend: file search and filter in Panel 1 | P1 |
| L2.10 | Frontend: Panel 2 text search (Ctrl+F) | P1 |
| L2.11 | Background processing with asyncio.create_task | P0 |
| L2.12 | SSE status stream for real-time processing updates | P0 |
| L2.13 | Tests: editing, notes, search, background processing | P0 |

**Gate L2:** Full three-panel UX working. Upload 50 files, edit text, add notes, navigate, search. All 7 file types extracting correctly.

#### Phase L3: Chat with Case (Target: 1-2 weeks)
> **Goal:** Add conversational AI that knows the case files and notes.

| Task | Description | Priority |
|------|------------|----------|
| L3.1 | CaseFileChunker: page-aware chunking for case files | P0 |
| L3.2 | Case file embedding: chunk, embed, store in `case_embeddings` | P0 |
| L3.3 | Re-embedding on text edit (debounced background task) | P0 |
| L3.4 | CaseChatService: dual-context retrieval (case files + knowledge base) | P0 |
| L3.5 | casefile_system.j2 prompt template | P0 |
| L3.6 | API: case chat endpoints (SSE streaming) | P0 |
| L3.7 | Frontend: chat drawer with streaming responses | P0 |
| L3.8 | Clickable file citations in chat responses → Panel 2 navigation | P1 |
| L3.9 | Suggested questions (contextual) | P1 |
| L3.10 | Chat session persistence | P1 |
| L3.11 | Tests: retrieval, chat, citation linking, prompt construction | P0 |

**Gate L3:** Ask questions about case files and get accurate, cited answers. AI uses both case files and knowledge base. Notes included in context.

#### Phase L4: Workflow Integration (Target: 2-3 weeks)
> **Goal:** Connect case context to workflows. Start with the highest-value ones.

| Task | Description | Priority |
|------|------------|----------|
| L4.1 | CaseContext value object + to_prompt_context() | P0 |
| L4.2 | Workflow: "Generate Case Analysis" (structured output: claims, elements, evidence) | P0 |
| L4.3 | Workflow: "Build Timeline" (extract dates/events, chronological output) | P1 |
| L4.4 | Integration: Objection Drafter receives CaseContext (pre-populate case info) | P1 |
| L4.5 | Workflow: "Draft Demand Letter" (SSE streaming, file + statute citations) | P1 |
| L4.6 | Frontend: workflow launcher (Actions dropdown) | P0 |
| L4.7 | Frontend: workflow result views (reuse answer-display patterns) | P0 |
| L4.8 | Export: workflow output as DOCX | P1 |
| L4.9 | Tests: workflows, integration, export | P0 |

**Gate L4:** End-to-end flow: upload files → edit → annotate → chat → generate case analysis → export DOCX.

#### Phase L5: Scale & Polish (Target: 2-3 weeks)
> **Goal:** Handle 100+ files, performance optimization, production readiness.

| Task | Description | Priority |
|------|------------|----------|
| L5.1 | Virtualized file list (react-window) for 100+ files | P0 |
| L5.2 | Virtualized text panel (intersection observer lazy loading) | P0 |
| L5.3 | Folder structure preservation (drag folder → preserve hierarchy) | P1 |
| L5.4 | Batch upload progress bar | P1 |
| L5.5 | PowerPointExtractor | P2 |
| L5.6 | Email attachment recursive extraction | P1 |
| L5.7 | File re-upload (replace file, re-extract) | P2 |
| L5.8 | Export composite text as DOCX/PDF | P2 |
| L5.9 | Responsive design (tablet, mobile read-only) | P2 |
| L5.10 | Performance benchmarks: 100 files upload + extract + embed < 5 min | P0 |
| L5.11 | End-to-end Playwright tests (full user journey) | P0 |

**Gate L5:** Production-ready LITIGAGENT. 100+ files, performant, polished.

### 13.3 Estimated Scope

| Phase | Duration | Backend | Frontend | Tests |
|-------|----------|---------|----------|-------|
| L1 | 1-2 weeks | ~800 lines | ~1200 lines | ~150 tests |
| L2 | 1-2 weeks | ~500 lines | ~800 lines | ~120 tests |
| L3 | 1-2 weeks | ~600 lines | ~600 lines | ~100 tests |
| L4 | 2-3 weeks | ~700 lines | ~500 lines | ~80 tests |
| L5 | 2-3 weeks | ~300 lines | ~600 lines | ~50 tests |
| **Total** | **7-12 weeks** | **~2900 lines** | **~3700 lines** | **~500 tests** |

---

## 14. Testing Strategy

### 14.1 Test Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E ╲           ~30 Playwright tests
                 ╱  tests ╲         (full user journeys)
                ╱──────────╲
               ╱ Integration ╲      ~100 tests
              ╱    tests      ╲     (API + storage + embedding)
             ╱────────────────╲
            ╱    Unit tests     ╲   ~370 tests
           ╱   (extractors,      ╲  (pure logic, no I/O)
          ╱    chunker, models)   ╲
         ╱────────────────────────╲
```

### 14.2 Test Categories

**Unit tests (no I/O):**
- Each extractor: known input bytes → expected text output
- Chunker: boundary detection, token counting, heading paths
- Domain models: validation, state transitions
- CaseContext: serialization, token budget management

**Integration tests:**
- API routes: file upload, text retrieval, note CRUD, chat
- Storage: SQLite CRUD, cascade deletes, case isolation
- Embedding: chunk → embed → search round-trip
- Background processing: upload → process → status update flow

**End-to-end tests (Playwright):**
- Upload 5 files via drag-and-drop → verify extraction
- Edit text → verify save persists
- Add note → verify display
- Chat with case → verify response includes file citations
- Navigate: click file → Panel 2 scrolls
- Full journey: upload → edit → annotate → chat → workflow → export

### 14.3 Test Data

Create a `tests/fixtures/casefile/` directory with sample files:
- `sample.pdf` (3-page text PDF)
- `scanned.pdf` (1-page scanned image PDF for OCR)
- `report.docx` (Word document with tables and headings)
- `data.xlsx` (Excel with 2 sheets)
- `email.eml` (Email with 1 attachment)
- `outlook.msg` (Outlook email)
- `photo.png` (Image with text for OCR)
- `notes.txt` (Plain text file)

---

## 15. Metrics & Success Criteria

### 15.1 MVP Success Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| **File extraction accuracy** | >95% text fidelity for non-OCR files | Compare extracted text to source (automated test) |
| **OCR accuracy** | >85% character accuracy for scanned PDFs | Compare OCR output to ground truth (sample test) |
| **Processing speed** | <3s per file (non-OCR), <10s per page (OCR) | Backend timing logs |
| **Upload-to-chat time** | <2 min for 20-file case | E2E timing test |
| **Chat answer relevance** | >80% of answers cite correct case files | Human evaluation (5 test cases) |
| **User task completion** | Upload + edit + note + chat in <10 min | Usability test with 5 attorneys |
| **Return rate** | >60% of testers return within 7 days | Usage tracking |

### 15.2 Business Metrics (Post-Launch)

| Metric | 3-Month Target | 12-Month Target |
|--------|---------------|-----------------|
| Cases created | 100 | 2,000 |
| Files uploaded | 2,000 | 50,000 |
| Chat questions asked | 500 | 20,000 |
| Workflows completed | 50 | 2,000 |
| Paying users (attorney) | 20 | 200 |
| Monthly revenue | $4,000 | $40,000 |
| NPS | >40 | >50 |

### 15.3 Cost Model

| Operation | Cost | Volume Estimate (per case) |
|-----------|------|--------------------------|
| Embedding (case files) | ~$0 (local CPU) | 200 chunks × 0.3s = 60s |
| Chat (Sonnet 4.6) | ~$0.03/query | 20 questions = $0.60 |
| Workflow (Sonnet 4.6) | ~$0.05/generation | 3 workflows = $0.15 |
| Storage (files + DB) | ~$0 (local disk) | ~50MB per case |
| **Total per case** | **~$0.75** | — |

At $200/mo subscription → ~267 cases per user to break even on LLM costs. Highly profitable.

---

## 16. Risk Assessment

### 16.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **OCR quality on poor scans** | High | Medium | Show confidence indicators. Let attorney edit. Offer re-processing with different settings. |
| **Large file processing time** | Medium | Medium | Background processing with progress. Async architecture. Set expectations in UI. |
| **Context window limits for large cases** | High | High | Retrieval-based context (not full dump). Map-reduce for summaries. Smart chunking. |
| **LanceDB performance at scale** | Low | High | Separate table per case (if needed). Benchmark at 100+ cases. |
| **Concurrent file processing** | Medium | Medium | Semaphore to limit concurrent OCR tasks (CPU-bound). Queue overflow handling. |
| **Memory pressure from embedding + OCR** | Medium | High | Process files sequentially within a case. Don't load embedding model during OCR (if RAM-constrained). |

### 16.2 Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Attorneys don't trust AI with privileged files** | Medium | Critical | Transparent data handling policy. No training on user data. Audit trail. On-premise option (future). |
| **Three-panel UX is overwhelming** | Medium | High | Progressive disclosure. Start with two panels (files + text). Notes as collapsible. Chat as overlay. |
| **Extraction errors erode trust** | High | High | Editable text is the antidote. OCR confidence indicators. "Reset to original" button. |
| **Competitors ship similar feature** | High | Medium | Speed of execution. Tight integration with employment law KB. File-to-workflow pipeline is our moat. |
| **Low frequency of new cases** | Medium | Medium | Focus on high-volume practices (insurance defense, PI). Multiple cases per attorney per month. |

### 16.3 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Low willingness to pay** | Medium | High | Validate with pre-sale test. Start with generous free tier. |
| **LLM costs spike** | Low | Medium | Token budget management. Model flexibility (can swap to cheaper model). |
| **Regulatory changes on AI in law** | Medium | High | Conservative disclaimers. Human-in-the-loop design (attorney edits everything). |
| **Data breach** | Low | Critical | Encryption at rest. Minimal data retention. Security audit before launch. |

---

## 17. Future Roadmap

### Near-term (Post-MVP, 3-6 months)

| Feature | Description | Value |
|---------|-------------|-------|
| **Case sharing** | Share cases with co-counsel (read-only or edit) | Collaboration, viral growth |
| **Document classification** | Auto-tag files (medical, financial, correspondence, pleading) | Faster navigation |
| **Smart highlights** | AI highlights key passages across all files | Saves reading time |
| **Comparative analysis** | "Compare what the police report says vs. the witness statement" | Credibility analysis |
| **Chronological timeline** | Visual timeline extracted from all documents | Case visualization |
| **Template system** | Save and reuse workflow templates (e.g., "demand letter for wrongful termination") | Efficiency for repeat case types |

### Mid-term (6-12 months)

| Feature | Description | Value |
|---------|-------------|-------|
| **Team workspaces** | Firm-level case management with role-based access | Enterprise readiness |
| **Knowledge base per firm** | Upload firm playbooks, templates, and reference materials (like Supio's Knowledge Bases) | Institutional knowledge |
| **Deposition prep** | Generate deposition outlines from case files | High-value workflow |
| **Brief writing** | Generate motion briefs with case file facts + legal research | High-value workflow |
| **Multi-state expansion** | Extend beyond California employment law | Market expansion |
| **Integration API** | REST API for case management system integration (Clio, MyCase, PracticePanther) | Distribution channel |

### Long-term (12+ months)

| Feature | Description | Value |
|---------|-------------|-------|
| **On-premise deployment** | Docker-based self-hosted option for security-sensitive firms | Enterprise sales |
| **Local LLM option** | Ollama/llama.cpp for zero-cloud processing | Maximum security |
| **Real-time collaboration** | Multiple attorneys editing notes and chatting simultaneously | Google Docs for legal |
| **Case outcome prediction** | Based on document analysis + historical data | Premium feature |
| **Auto-discovery** | AI generates discovery requests based on case analysis | Full automation |
| **Court filing integration** | Direct e-filing from LITIGAGENT | End-to-end workflow |

---

## Appendix A: Competitive Feature Matrix

| Feature | LITIGAGENT | FilevineAI | CoCounsel | Harvey | Supio | Everlaw |
|---------|-----------|-----------|-----------|--------|-------|---------|
| Standalone file ingestion | ✅ | ❌ (Filevine only) | ❌ | Partial | ❌ | ✅ |
| Drag-and-drop upload | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Editable extracted text | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| OCR with confidence | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Attorney notes layer | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Chat with case files | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Knowledge base integration | ✅ | ❌ | ✅ (Westlaw) | ❌ | ❌ | ❌ |
| File → Workflow pipeline | ✅ | ❌ | Partial | Partial | ✅ (PI only) | Partial |
| Demand letter generation | ✅ | ❌ | ❌ | ✅ | ✅ (PI only) | ❌ |
| Discovery preparation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Case analysis | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Timeline generation | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Employment law depth | ✅✅ | ❌ | ✅ (generic) | ✅ (generic) | ❌ | ❌ |
| Pricing | $200/mo | +$39-79/mo (Filevine) | Enterprise | Enterprise | Per case | Per GB |

---

## Appendix B: Key Decisions Log

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| Storage for files | Local disk | Files >1MB, BLOBs in SQLite anti-pattern. Simple. Reversible. | S3 (premature for MVP), SQLite BLOBs (poor perf) |
| Separate LanceDB table | `case_embeddings` | Case files must not pollute KB search. Case-scoped queries. | Same table with filter (mixing concerns), separate DB (unnecessary) |
| Chunking size | 1000 tokens | Case files need precision retrieval. Smaller chunks = more precise answers. | 1500 (KB standard, too coarse for case files), 500 (too small, loses context) |
| Background processing | asyncio.create_task | Simple. No external dependencies. Sufficient for single-user MVP. | Celery+Redis (premature), threading (GIL), subprocess (complexity) |
| Text editing model | `edited_text` as canonical | Attorney's corrections are authoritative. Preserve original for re-extraction. | Single `text` field (loses original), version history (premature) |
| Chat context strategy | Retrieval-based | Context window limits. 100 files = 2M+ tokens. Must retrieve relevant chunks. | Full context dump (impossible), summarize-then-chat (lossy) |
| Prompt architecture | Separate case template | Case chat needs different instructions than KB chat. | Extend existing prompts (mixing concerns) |
| Panel 3 (Notes) scope | Case + file notes | Simple. Covers both general context and file-specific annotations. | Threaded comments (complexity), highlight-based annotations (UI complexity) |

---

## Appendix C: Research Sources

### Market & Competitive Intelligence
- [Spellbook: 9 Best Legal AI Tools 2026](https://www.spellbook.legal/learn/legal-ai-tools)
- [Briefpoint: Best AI for Legal Documents 2026](https://briefpoint.ai/best-ai-for-legal-documents/)
- [FilevineAI: Chat with Your Case (LawSites)](https://www.lawnext.com/2025/05/filevine-launches-the-only-embedded-ai-legal-assistant-that-lets-legal-professionals-chat-with-their-case.html)
- [ChronoVault: AI Case Prep (LawSites)](https://www.lawnext.com/2025/08/nexlaw-ais-chronovault-redefines-legal-case-prep-with-ai-powered-insights.html)
- [ABA TECHSHOW 2026 Startup Alley (LawSites)](https://www.lawnext.com/2026/02/the-votes-are-in-here-are-the-15-legal-tech-startups-selected-for-the-2026-startup-alley-at-aba-techshow.html)
- [Harvey AI vs. CoCounsel Comparison](https://www.aline.co/post/harvey-ai-vs-cocounsel)
- [Legal AI Benchmark Study (LawSites)](https://www.lawnext.com/2025/02/legal-ai-tools-show-promise-in-first-of-its-kind-benchmark-study-with-harvey-and-cocounsel-leading-the-pack.html)
- [Clio/Harvey AI Alternatives](https://www.clio.com/blog/harvey-ai-legal/)
- [Everlaw AI Features](https://www.everlaw.com/product/everlaw-ai/)
- [Everlaw Deep Dive GA Announcement](https://www.lawnext.com/2025/11/everlaw-announces-general-availability-of-ai-deep-dive-as-well-as-major-pricing-changes-at-annual-summit.html)
- [Supio AI Features Launch (2026)](https://www.prnewswire.com/news-releases/supio-launches-ai-powered-features-to-cut-case-prep-costs-and-strengthen-settlement-leverage-302692248.html)
- [Smokeball: 8 Legal AI Tools 2026](https://www.smokeball.com/blog/10-ai-apps-for-your-legal-toolbox)
- [Legal AI Adoption: 37% (2024) → 80% (2025)](https://www.netdocuments.com/blog/2026-legal-tech-trends/)
- [RAG Hallucination in Legal AI (Stanford)](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf)
- [LexRAG: Multi-Turn Legal Consultation Benchmark](https://dl.acm.org/doi/10.1145/3726302.3730340)
- [AI-Generated Documents Lack Privilege (Heppner)](https://www.dlapiper.com/en-us/insights/publications/2026/02/are-ai-generated-documents-privileged-key-takeaways-from-heppner)

### Technical
- [Apple Split View Guidelines](https://developer.apple.com/design/human-interface-guidelines/split-views)
- [Cloudscape Split View Pattern](https://cloudscape.design/patterns/resource-management/view/split-view/)
- [OCRmyPDF (PyPI)](https://pypi.org/project/ocrmypdf/)
- [extract-msg (PyPI)](https://pypi.org/project/extract-msg/)
- [Python email.parser Documentation](https://docs.python.org/3/library/email.parser.html)
