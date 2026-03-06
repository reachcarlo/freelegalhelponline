"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import {
  useObjectionDrafter,
} from "@/lib/objection-context";
import {
  DISCOVERY_TYPE_LABELS,
  VERBOSITY_LABELS,
  POSTURE_LABELS,
  parseRequests,
  parseDocument,
  generateObjections,
  type ResponseDiscoveryType,
  type Verbosity,
  type PartyRole,
  type LitigationPosture,
} from "@/lib/objection-api";
import WizardStepper from "./wizard-stepper";
import ObjectionParsePreview from "./objection-parse-preview";
import ObjectionResults from "./objection-results";

const STEPS = [
  { label: "Setup" },
  { label: "Input" },
  { label: "Review" },
  { label: "Results" },
];

export default function ObjectionDrafter() {
  const { state, dispatch, nextStep, prevStep, setStep, selectedCount } =
    useObjectionDrafter();

  // ── Parse handler ────────────────────────────────────────────────
  const handleParse = useCallback(async () => {
    const hasFile = !!state.uploadedFile;
    const hasText = state.rawText.trim().length > 0;
    if (!hasFile && !hasText) return;

    dispatch({ type: "PARSE_START" });
    try {
      const dtype =
        state.discoveryType === "auto"
          ? undefined
          : (state.discoveryType as ResponseDiscoveryType);

      const result = hasFile
        ? await parseDocument(state.uploadedFile!, dtype)
        : await parseRequests(state.rawText, dtype);

      dispatch({
        type: "PARSE_SUCCESS",
        requests: result.requests,
        skippedSections: result.skipped_sections,
        metadata: result.metadata,
        detectedType: result.detected_type,
        isResponseShell: result.is_response_shell,
        warnings: result.warnings,
      });
    } catch (err) {
      dispatch({
        type: "PARSE_ERROR",
        error: err instanceof Error ? err.message : "Failed to parse requests",
      });
    }
  }, [state.rawText, state.uploadedFile, state.discoveryType, dispatch]);

  // ── Generate handler ─────────────────────────────────────────────
  const handleGenerate = useCallback(async () => {
    const selected = state.parsedRequests.filter((r) =>
      state.selectedRequestIds.has(r.id)
    );
    if (selected.length === 0) return;

    dispatch({ type: "GENERATE_START" });
    try {
      const response = await generateObjections({
        requests: selected.map((r) => ({
          request_number:
            typeof r.request_number === "number"
              ? r.request_number
              : parseInt(String(r.request_number), 10) || 1,
          request_text: r.request_text,
          discovery_type: r.discovery_type,
        })),
        verbosity: state.verbosity,
        party_role: state.partyRole,
        posture: state.posture,
        include_request_text:
          state.contentScope === "request_and_objections",
        include_waiver_language: state.includeWaiverLanguage,
      });
      dispatch({ type: "GENERATE_SUCCESS", response });
    } catch (err) {
      dispatch({
        type: "GENERATE_ERROR",
        error:
          err instanceof Error ? err.message : "Failed to generate objections",
      });
    }
  }, [
    state.parsedRequests,
    state.selectedRequestIds,
    state.verbosity,
    state.partyRole,
    state.posture,
    state.contentScope,
    state.includeWaiverLanguage,
    dispatch,
  ]);

  // ── Navigation guards ────────────────────────────────────────────
  const canAdvanceFromSetup = true; // Setup has valid defaults
  const canAdvanceFromInput =
    state.rawText.trim().length > 0 || !!state.uploadedFile;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border bg-surface px-4 py-3 sm:px-6">
        <nav className="mb-2 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <Link href="/tools" className="hover:text-accent">
            Tools
          </Link>
          {" / "}
          <Link href="/tools/discovery" className="hover:text-accent">
            Discovery
          </Link>
          {" / "}
          <span className="text-text-primary">Objection Drafter</span>
        </nav>
        <WizardStepper steps={STEPS} currentStep={state.currentStep} />
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
          {state.error && (
            <div className="mb-4 rounded-lg border border-error-border bg-error-bg px-4 py-3 text-sm text-error-text">
              {state.error}
              <button
                onClick={() => dispatch({ type: "CLEAR_ERROR" })}
                className="ml-2 font-medium underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {state.currentStep === 0 && <SetupStep />}
          {state.currentStep === 1 && (
            <InputStep onParse={handleParse} isParsing={state.isParsing} />
          )}
          {state.currentStep === 2 && <ObjectionParsePreview />}
          {state.currentStep === 3 && <ObjectionResults />}
        </div>
      </div>

      {/* Navigation footer */}
      <div className="flex items-center justify-between border-t border-border bg-surface px-4 py-3 sm:px-6">
        {/* Back / Exit */}
        {state.currentStep === 0 ? (
          <Link
            href="/tools/discovery"
            className="min-h-[44px] min-w-[44px] inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-accent-surface hover:text-accent transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            &larr; Exit
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => {
              if (state.currentStep === 3) {
                // Going back from Results to Review
                setStep(2);
              } else {
                prevStep();
              }
            }}
            className="min-h-[44px] min-w-[44px] rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-accent-surface hover:text-accent transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            Back
          </button>
        )}

        {/* Center */}
        <span className="text-xs text-text-tertiary">
          {state.currentStep + 1} / {STEPS.length}
        </span>

        {/* Next / Parse / Generate */}
        {state.currentStep === 0 && (
          <button
            type="button"
            onClick={nextStep}
            disabled={!canAdvanceFromSetup}
            className={`min-h-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
              canAdvanceFromSetup
                ? "bg-accent text-white hover:bg-accent-hover"
                : "cursor-not-allowed bg-accent/30 text-text-tertiary"
            }`}
          >
            Next
          </button>
        )}
        {state.currentStep === 1 && (
          <button
            type="button"
            onClick={handleParse}
            disabled={!canAdvanceFromInput || state.isParsing}
            className={`min-h-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
              canAdvanceFromInput && !state.isParsing
                ? "bg-accent text-white hover:bg-accent-hover"
                : "cursor-not-allowed bg-accent/30 text-text-tertiary"
            }`}
          >
            {state.isParsing ? (
              <span className="flex items-center gap-2">
                <Spinner /> Parsing…
              </span>
            ) : (
              "Parse Requests"
            )}
          </button>
        )}
        {state.currentStep === 2 && (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={selectedCount === 0 || state.isGenerating}
            className={`min-h-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
              selectedCount > 0 && !state.isGenerating
                ? "bg-accent text-white hover:bg-accent-hover"
                : "cursor-not-allowed bg-accent/30 text-text-tertiary"
            }`}
          >
            {state.isGenerating ? (
              <span className="flex items-center gap-2">
                <Spinner /> Generating…
              </span>
            ) : (
              `Generate Objections (${selectedCount})`
            )}
          </button>
        )}
        {state.currentStep === 3 && (
          <button
            type="button"
            onClick={() => dispatch({ type: "RESET" })}
            className="min-h-[44px] rounded-lg px-5 py-2 text-sm font-semibold border border-border text-text-secondary hover:bg-accent-surface transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            Start Over
          </button>
        )}
      </div>
    </div>
  );
}

// ── Spinner ──────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ── Step 1: Setup ────────────────────────────────────────────────────

function SetupStep() {
  const { state, dispatch } = useObjectionDrafter();

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-text-primary">
          Objection Drafter Setup
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Configure your objection preferences before pasting discovery requests.
        </p>
      </div>

      {/* Discovery Type */}
      <fieldset>
        <legend className="text-sm font-medium text-text-primary mb-3">
          Discovery Type
        </legend>
        <div className="flex flex-wrap gap-2">
          {(
            [
              { value: "auto" as const, label: "Auto-detect" },
              ...Object.entries(DISCOVERY_TYPE_LABELS).map(([v, l]) => ({
                value: v as ResponseDiscoveryType,
                label: l,
              })),
            ] as { value: ResponseDiscoveryType | "auto"; label: string }[]
          ).map((opt) => {
            const selected = state.discoveryType === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() =>
                  dispatch({
                    type: "SET_DISCOVERY_TYPE",
                    discoveryType: opt.value,
                  })
                }
                className={`min-h-[44px] rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                  selected
                    ? "border-accent bg-accent-surface text-accent"
                    : "border-border text-text-secondary hover:border-border-hover"
                }`}
                aria-pressed={selected}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Verbosity */}
      <fieldset>
        <legend className="text-sm font-medium text-text-primary mb-3">
          Verbosity
        </legend>
        <div className="grid grid-cols-3 gap-3">
          {(Object.entries(VERBOSITY_LABELS) as [Verbosity, { label: string; description: string }][]).map(
            ([key, info]) => {
              const selected = state.verbosity === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() =>
                    dispatch({ type: "SET_VERBOSITY", verbosity: key })
                  }
                  className={`min-h-[44px] rounded-lg border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                    selected
                      ? "border-accent bg-accent-surface"
                      : "border-border hover:border-border-hover"
                  }`}
                  aria-pressed={selected}
                >
                  <span
                    className={`text-sm font-medium ${
                      selected ? "text-accent" : "text-text-primary"
                    }`}
                  >
                    {info.label}
                  </span>
                  <span className="mt-1 block text-xs text-text-tertiary">
                    {info.description}
                  </span>
                </button>
              );
            }
          )}
        </div>
      </fieldset>

      {/* Party Role */}
      <fieldset>
        <legend className="text-sm font-medium text-text-primary mb-3">
          Party Role
        </legend>
        <div className="grid grid-cols-2 gap-3">
          {(
            [
              {
                value: "plaintiff" as PartyRole,
                label: "Plaintiff",
                description: "You represent the plaintiff",
              },
              {
                value: "defendant" as PartyRole,
                label: "Defendant",
                description: "You represent the defendant",
              },
            ]
          ).map((role) => {
            const selected = state.partyRole === role.value;
            return (
              <button
                key={role.value}
                type="button"
                onClick={() =>
                  dispatch({
                    type: "SET_PARTY_ROLE",
                    partyRole: role.value,
                  })
                }
                className={`min-h-[44px] rounded-lg border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                  selected
                    ? "border-accent bg-accent-surface"
                    : "border-border hover:border-border-hover"
                }`}
                aria-pressed={selected}
              >
                <span
                  className={`text-sm font-medium ${
                    selected ? "text-accent" : "text-text-primary"
                  }`}
                >
                  {role.label}
                </span>
                <span className="mt-1 block text-xs text-text-tertiary">
                  {role.description}
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Litigation Posture */}
      <fieldset>
        <legend className="text-sm font-medium text-text-primary mb-3">
          Litigation Posture
        </legend>
        <div className="grid grid-cols-3 gap-3">
          {(Object.entries(POSTURE_LABELS) as [LitigationPosture, { label: string; description: string; tooltip: string }][]).map(
            ([key, info]) => {
              const selected = state.posture === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() =>
                    dispatch({ type: "SET_POSTURE", posture: key })
                  }
                  title={info.tooltip}
                  className={`min-h-[44px] rounded-lg border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                    selected
                      ? "border-accent bg-accent-surface"
                      : "border-border hover:border-border-hover"
                  }`}
                  aria-pressed={selected}
                >
                  <span
                    className={`text-sm font-medium ${
                      selected ? "text-accent" : "text-text-primary"
                    }`}
                  >
                    {info.label}
                  </span>
                  <span className="mt-1 block text-xs text-text-tertiary">
                    {info.description}
                  </span>
                </button>
              );
            }
          )}
        </div>
      </fieldset>

      {/* "Subject to and without waiving" toggle */}
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={state.includeWaiverLanguage}
          onClick={() =>
            dispatch({
              type: "SET_WAIVER_LANGUAGE",
              include: !state.includeWaiverLanguage,
            })
          }
          className={`relative mt-0.5 inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
            state.includeWaiverLanguage ? "bg-accent" : "bg-border"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
              state.includeWaiverLanguage ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
        <div>
          <span className="text-sm font-medium text-text-primary">
            &ldquo;Subject to and without waiving&rdquo; preamble
          </span>
          <p className="mt-0.5 text-xs text-text-tertiary">
            Appends: &ldquo;Subject to and without waiving the foregoing
            objections, Responding Party responds as follows:&hellip;&rdquo;
            California courts have criticized boilerplate preambles. See{" "}
            <em>Korea Data Systems Co. v. Superior Court</em> (1997) 51
            Cal.App.4th 1513.
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Step 2: Input ────────────────────────────────────────────────────

const ACCEPTED_TYPES = ".docx,.pdf";
const MAX_FILE_SIZE_MB = 10;

function InputStep({
  onParse,
  isParsing,
}: {
  onParse: () => void;
  isParsing: boolean;
}) {
  const { state, dispatch } = useObjectionDrafter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const hasFile = !!state.uploadedFile;
  const hasInput = hasFile || state.rawText.trim().length > 0;

  const handleFile = useCallback(
    (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "docx" && ext !== "pdf") {
        dispatch({
          type: "PARSE_ERROR",
          error: "Only .docx and .pdf files are accepted.",
        });
        return;
      }
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        dispatch({
          type: "PARSE_ERROR",
          error: `File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`,
        });
        return;
      }
      dispatch({ type: "SET_UPLOADED_FILE", file });
    },
    [dispatch]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-text-primary">
          Upload or Paste Discovery Requests
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Upload a .docx or .pdf file, or paste text below. The parser will
          extract individual requests, skip definitions, instructions, captions,
          and proof of service.
        </p>
      </div>

      {/* File drop zone / uploaded file card */}
      {hasFile ? (
        <div className="flex items-center gap-3 rounded-lg border border-accent bg-accent-surface px-4 py-3">
          <svg className="h-5 w-5 text-accent shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary truncate">
              {state.uploadedFileName}
            </p>
            <p className="text-xs text-text-tertiary">
              {formatFileSize(state.uploadedFile!.size)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => dispatch({ type: "CLEAR_UPLOADED_FILE" })}
            className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium border border-border text-text-secondary hover:bg-surface transition-colors"
            aria-label="Remove uploaded file"
          >
            Remove
          </button>
        </div>
      ) : (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 cursor-pointer transition-colors ${
            isDragging
              ? "border-accent bg-accent-surface"
              : "border-border hover:border-border-hover"
          }`}
          role="button"
          aria-label="Upload .docx or .pdf file"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <svg className="h-8 w-8 text-text-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L8 8m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
          </svg>
          <p className="text-sm text-text-secondary">
            <span className="font-medium text-accent">Upload .docx or .pdf</span>
            {" "}or drag and drop
          </p>
          <p className="text-xs text-text-tertiary">Max {MAX_FILE_SIZE_MB} MB</p>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
            aria-label="File upload input"
          />
        </div>
      )}

      {/* Divider */}
      {!hasFile && (
        <>
          <div className="flex items-center gap-3">
            <div className="flex-1 border-t border-border" />
            <span className="text-xs text-text-tertiary">or paste text</span>
            <div className="flex-1 border-t border-border" />
          </div>

          <textarea
            value={state.rawText}
            onChange={(e) =>
              dispatch({ type: "SET_RAW_TEXT", text: e.target.value })
            }
            placeholder="Paste discovery requests here…&#10;&#10;Example:&#10;SPECIAL INTERROGATORY NO. 1:&#10;State all facts supporting your contention that…"
            className="w-full min-h-[200px] max-h-[500px] rounded-lg border border-border bg-input-bg px-4 py-3 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none resize-y"
            aria-label="Discovery request text"
            style={{
              height: state.rawText.length > 500 ? "400px" : undefined,
            }}
          />

          <p className="text-xs text-text-tertiary">
            {state.rawText.length > 0 && (
              <span className="font-medium">
                {state.rawText.length.toLocaleString()} characters
              </span>
            )}
          </p>
        </>
      )}

      {/* Unsupported format notice */}
      <div className="rounded-lg border border-border bg-surface px-4 py-3 text-xs text-text-tertiary">
        Supports typed discovery text — interrogatories, RFPs, and RFAs.
        Scanned forms and Judicial Council checkbox forms (DISC-001 series)
        require manual entry of each request.
      </div>

      {/* Parse button (also in footer, but helpful inline) */}
      {hasInput && (
        <button
          type="button"
          onClick={onParse}
          disabled={isParsing}
          className={`w-full min-h-[44px] rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
            isParsing
              ? "cursor-not-allowed bg-accent/30 text-text-tertiary"
              : "bg-accent text-white hover:bg-accent-hover"
          }`}
        >
          {isParsing ? "Parsing…" : "Parse Requests"}
        </button>
      )}
    </div>
  );
}
