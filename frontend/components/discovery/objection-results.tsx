"use client";

import { useState } from "react";
import { useObjectionDrafter } from "@/lib/objection-context";
import {
  STRENGTH_LABELS,
  DISCOVERY_TYPE_LABELS,
  copyToClipboard,
  downloadTextFile,
  downloadBlob,
  exportDocx,
  type ContentScope,
  type ObjectionStrength,
  type RequestAnalysisInfo,
  type ResponseDiscoveryType,
} from "@/lib/objection-api";

export default function ObjectionResults() {
  const { state, dispatch } = useObjectionDrafter();
  const { generateResponse, contentScope, objectionToggles, isExporting } = state;

  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedRequest, setCopiedRequest] = useState<string | null>(null);
  const [expandedPanels, setExpandedPanels] = useState<Set<number>>(() => {
    // First result expanded by default
    return new Set(generateResponse?.results.length ? [0] : []);
  });

  if (!generateResponse) return null;

  const { results, disclaimer, model_used, duration_ms, cost_estimate } =
    generateResponse;

  const totalObjections = results.reduce(
    (acc, r) => acc + r.objections.length,
    0
  );

  const enabledObjections = results.reduce((acc, r) => {
    return (
      acc +
      r.objections.filter(
        (o) => objectionToggles[`${r.request_number}-${o.ground_id}`] !== false
      ).length
    );
  }, 0);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-text-primary">
          Generated Objections
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          {totalObjections} objection{totalObjections !== 1 ? "s" : ""} across{" "}
          {results.length} request{results.length !== 1 ? "s" : ""}
          {model_used && (
            <span className="text-text-tertiary">
              {" "}
              &middot; {model_used} &middot;{" "}
              {(duration_ms / 1000).toFixed(1)}s
              {cost_estimate > 0 && ` · $${cost_estimate.toFixed(4)}`}
            </span>
          )}
        </p>
      </div>

      {/* Content scope toggle */}
      <ContentScopeToggle
        value={contentScope}
        onChange={(scope) =>
          dispatch({ type: "SET_CONTENT_SCOPE", scope })
        }
      />

      {/* Warnings */}
      {generateResponse.warnings.length > 0 && (
        <div className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
          {generateResponse.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      {/* Request accordion */}
      <div className="space-y-2">
        {results.map((result, idx) => (
          <RequestPanel
            key={result.request_number}
            result={result}
            isExpanded={expandedPanels.has(idx)}
            onToggleExpand={() =>
              setExpandedPanels((prev) => {
                const next = new Set(prev);
                if (next.has(idx)) next.delete(idx);
                else next.add(idx);
                return next;
              })
            }
            contentScope={contentScope}
            objectionToggles={objectionToggles}
            onToggleObjection={(key) =>
              dispatch({ type: "TOGGLE_OBJECTION", key })
            }
            copied={copiedRequest === String(result.request_number)}
            onCopy={() => {
              const text = buildRequestText(
                result,
                contentScope,
                objectionToggles
              );
              copyToClipboard(text);
              setCopiedRequest(String(result.request_number));
              setTimeout(() => setCopiedRequest(null), 2000);
            }}
          />
        ))}
      </div>

      {/* Disclaimer */}
      <div className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
        {disclaimer}
      </div>

      {/* Sticky summary bar */}
      <div className="sticky bottom-0 -mx-4 sm:-mx-6 bg-surface border-t border-border px-4 sm:px-6 py-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <span className="text-sm text-text-secondary">
            {enabledObjections} of {totalObjections} objections enabled
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => {
                const text = buildAllText(results, contentScope, objectionToggles);
                copyToClipboard(text);
                setCopiedAll(true);
                setTimeout(() => setCopiedAll(false), 2000);
              }}
              className={`min-h-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                copiedAll
                  ? "bg-verified-bg text-verified-text border border-verified-border"
                  : "bg-accent text-white hover:bg-accent-hover"
              }`}
            >
              {copiedAll ? "Copied!" : "Copy All"}
            </button>
            <button
              type="button"
              onClick={() => {
                const text = buildAllText(results, contentScope, objectionToggles);
                downloadTextFile(text, "objections.txt");
              }}
              className="min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-accent-surface transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              Download .txt
            </button>
            <button
              type="button"
              disabled={isExporting}
              onClick={async () => {
                dispatch({ type: "EXPORT_START" });
                try {
                  const { blob, filename } = await exportDocx({
                    results,
                    format: "docx_standalone",
                    includeRequestText: contentScope === "request_and_objections",
                    includeWaiverLanguage: state.includeWaiverLanguage,
                    enabledObjections: objectionToggles,
                  });
                  downloadBlob(blob, filename);
                  dispatch({ type: "EXPORT_DONE" });
                } catch (err) {
                  dispatch({
                    type: "EXPORT_ERROR",
                    error: err instanceof Error ? err.message : "Export failed",
                  });
                }
              }}
              className={`min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                isExporting
                  ? "cursor-not-allowed opacity-50 text-text-tertiary"
                  : "text-text-secondary hover:bg-accent-surface"
              }`}
            >
              {isExporting ? "Exporting…" : "Download .docx"}
            </button>
            {state.uploadedFile && state.isResponseShell && (
              <button
                type="button"
                disabled={isExporting}
                onClick={async () => {
                  dispatch({ type: "EXPORT_START" });
                  try {
                    const { blob, filename } = await exportDocx({
                      results,
                      format: "docx_shell_insert",
                      includeRequestText: false,
                      includeWaiverLanguage: state.includeWaiverLanguage,
                      enabledObjections: objectionToggles,
                      shellFile: state.uploadedFile!,
                    });
                    downloadBlob(blob, filename);
                    dispatch({ type: "EXPORT_DONE" });
                  } catch (err) {
                    dispatch({
                      type: "EXPORT_ERROR",
                      error: err instanceof Error ? err.message : "Shell insert failed",
                    });
                  }
                }}
                className={`min-h-[44px] rounded-lg border border-accent px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                  isExporting
                    ? "cursor-not-allowed opacity-50 text-text-tertiary"
                    : "text-accent hover:bg-accent-surface"
                }`}
              >
                {isExporting ? "Inserting…" : "Insert into Shell"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Content Scope Toggle ─────────────────────────────────────────────

function ContentScopeToggle({
  value,
  onChange,
}: {
  value: ContentScope;
  onChange: (v: ContentScope) => void;
}) {
  const options: { value: ContentScope; label: string }[] = [
    { value: "objections_only", label: "Objections Only" },
    { value: "request_and_objections", label: "Request + Objections" },
  ];

  return (
    <div className="inline-flex rounded-lg border border-border p-0.5" role="radiogroup">
      {options.map((opt) => {
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(opt.value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              selected
                ? "bg-accent text-white"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Request Panel (Accordion) ────────────────────────────────────────

function RequestPanel({
  result,
  isExpanded,
  onToggleExpand,
  contentScope,
  objectionToggles,
  onToggleObjection,
  copied,
  onCopy,
}: {
  result: RequestAnalysisInfo;
  isExpanded: boolean;
  onToggleExpand: () => void;
  contentScope: ContentScope;
  objectionToggles: Record<string, boolean>;
  onToggleObjection: (key: string) => void;
  copied: boolean;
  onCopy: () => void;
}) {
  const enabledCount = result.objections.filter(
    (o) => objectionToggles[`${result.request_number}-${o.ground_id}`] !== false
  ).length;

  // Strength summary
  const strengthCounts: Record<ObjectionStrength, number> = {
    high: 0,
    medium: 0,
    low: 0,
  };
  for (const o of result.objections) {
    strengthCounts[o.strength as ObjectionStrength] =
      (strengthCounts[o.strength as ObjectionStrength] || 0) + 1;
  }

  const discoveryTypeLabel =
    DISCOVERY_TYPE_LABELS[result.discovery_type as ResponseDiscoveryType] ||
    result.discovery_type;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      {/* Accordion header */}
      <button
        type="button"
        onClick={onToggleExpand}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-accent-surface/50 transition-colors"
        aria-expanded={isExpanded}
      >
        <span
          className={`text-text-tertiary text-xs transition-transform ${
            isExpanded ? "rotate-90" : ""
          }`}
        >
          &#9654;
        </span>
        <span className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-text-primary">
            {discoveryTypeLabel.replace(/s$/, "").toUpperCase()} NO.{" "}
            {result.request_number}
          </span>
          <span className="ml-2 text-xs text-text-tertiary truncate">
            {result.request_text.slice(0, 60)}
            {result.request_text.length > 60 ? "…" : ""}
          </span>
        </span>
        <span className="flex items-center gap-1.5 shrink-0">
          {result.objections.length === 0 ? (
            <span className="text-xs text-text-tertiary">No objections</span>
          ) : (
            <>
              {strengthCounts.high > 0 && (
                <StrengthBadge strength="high" count={strengthCounts.high} />
              )}
              {strengthCounts.medium > 0 && (
                <StrengthBadge
                  strength="medium"
                  count={strengthCounts.medium}
                />
              )}
              {strengthCounts.low > 0 && (
                <StrengthBadge strength="low" count={strengthCounts.low} />
              )}
              <span className="ml-1 text-xs text-text-tertiary">
                {enabledCount}/{result.objections.length}
              </span>
            </>
          )}
        </span>
      </button>

      {/* Accordion body */}
      {isExpanded && (
        <div className="border-t border-border px-4 py-3 space-y-3">
          {/* Request text (when scope includes it) */}
          {contentScope === "request_and_objections" && (
            <div className="rounded-lg bg-surface px-3 py-2 text-xs text-text-secondary whitespace-pre-wrap border border-border">
              <p className="font-semibold text-text-tertiary mb-1 text-[10px] uppercase tracking-wide">
                Request Text
              </p>
              {result.request_text}
            </div>
          )}

          {/* No objections message */}
          {result.objections.length === 0 && result.no_objections_rationale && (
            <div className="rounded-lg bg-surface px-3 py-2 text-sm text-text-secondary italic">
              {result.no_objections_rationale}
            </div>
          )}
          {result.objections.length === 0 && !result.no_objections_rationale && (
            <p className="text-sm text-text-tertiary italic">
              No objection grounds appear to apply to this request.
            </p>
          )}

          {/* Objection cards */}
          {result.objections.map((obj) => {
            const toggleKey = `${result.request_number}-${obj.ground_id}`;
            const enabled = objectionToggles[toggleKey] !== false;

            return (
              <div
                key={obj.ground_id}
                className={`rounded-lg border p-3 transition-opacity ${
                  enabled
                    ? "border-border"
                    : "border-border opacity-40"
                }`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => onToggleObjection(toggleKey)}
                    className="mt-1 h-4 w-4 shrink-0 rounded border-border text-accent focus:ring-accent/40"
                    aria-label={`Include ${obj.label} objection`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StrengthBadge strength={obj.strength as ObjectionStrength} />
                      <span className="text-sm font-semibold text-text-primary">
                        {obj.label}
                      </span>
                      <span className="text-[10px] text-text-tertiary capitalize">
                        {obj.category}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-text-secondary">
                      {obj.explanation}
                    </p>

                    {/* Citations */}
                    {(obj.statutory_citations.length > 0 ||
                      obj.case_citations.length > 0) && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {obj.statutory_citations.map((c, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center rounded-full bg-accent-surface px-2 py-0.5 text-[10px] font-medium text-accent"
                          >
                            {c.code} {c.section}
                          </span>
                        ))}
                        {obj.case_citations.map((c, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center rounded-full bg-surface border border-border px-2 py-0.5 text-[10px] font-medium text-text-secondary"
                            title={c.citation}
                          >
                            <em>{c.name}</em>
                            <span className="ml-1 text-text-tertiary">
                              ({c.year})
                            </span>
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Citation warnings */}
                    {obj.citation_warnings.length > 0 && (
                      <div className="mt-1.5">
                        {obj.citation_warnings.map((w, i) => (
                          <p
                            key={i}
                            className="text-[10px] text-warning-text"
                          >
                            &#9888; {w}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Per-request copy */}
          {result.objections.length > 0 && (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onCopy}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                  copied
                    ? "bg-verified-bg text-verified-text border border-verified-border"
                    : "border border-border text-text-secondary hover:bg-accent-surface"
                }`}
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Strength Badge ───────────────────────────────────────────────────

function StrengthBadge({
  strength,
  count,
}: {
  strength: ObjectionStrength;
  count?: number;
}) {
  const style = STRENGTH_LABELS[strength];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${style.color} ${style.bg} ${style.border}`}
    >
      {style.label}
      {count != null && count > 0 && <span className="ml-0.5">{count}</span>}
    </span>
  );
}

// ── Text builders ────────────────────────────────────────────────────

function buildRequestText(
  result: RequestAnalysisInfo,
  contentScope: ContentScope,
  toggles: Record<string, boolean>
): string {
  const parts: string[] = [];

  if (contentScope === "request_and_objections") {
    parts.push(
      `REQUEST NO. ${result.request_number}:\n${result.request_text}\n`
    );
    parts.push(`RESPONSE TO REQUEST NO. ${result.request_number}:`);
  }

  const enabledObjections = result.objections.filter(
    (o) => toggles[`${result.request_number}-${o.ground_id}`] !== false
  );

  if (enabledObjections.length === 0) {
    if (result.no_objections_rationale) {
      parts.push(result.no_objections_rationale);
    }
  } else {
    for (const o of enabledObjections) {
      const statCites = o.statutory_citations
        .map((c) => `${c.code} ${c.section}`)
        .join(", ");
      const caseCites = o.case_citations
        .map((c) => `${c.name} ${c.citation}`)
        .join("; ");
      const cites = [statCites, caseCites].filter(Boolean).join("; ");
      parts.push(
        `Objection: ${o.label}: ${o.explanation}${cites ? ` (${cites})` : ""}`
      );
    }
  }

  return parts.join("\n");
}

function buildAllText(
  results: RequestAnalysisInfo[],
  contentScope: ContentScope,
  toggles: Record<string, boolean>
): string {
  return results
    .map((r) => buildRequestText(r, contentScope, toggles))
    .join("\n\n---\n\n");
}
