"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CaseContextInfo,
  CaseFactInfo,
  CaseFileInfo,
  confirmFact,
  getCaseContext,
  listFacts,
} from "@/lib/litigagent-api";

interface CaseInfoProps {
  caseId: string;
  files: CaseFileInfo[];
  onClose: () => void;
}

// ── Helpers ───────────────────────────────────────────────────

function sourceLabel(fileId: string | null, files: CaseFileInfo[]): string {
  if (!fileId) return "";
  const f = files.find((x) => x.id === fileId);
  return f ? f.original_filename : fileId;
}

function formatValue(value: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(value)) {
    if (v == null) continue;
    parts.push(`${k}: ${v}`);
  }
  return parts.join(" \u00b7 ");
}

function confidenceBadge(confidence: number): string {
  if (confidence >= 0.9) return "high";
  if (confidence >= 0.7) return "medium";
  return "low";
}

// ── Section components ────────────────────────────────────────

function SectionHeader({
  title,
  count,
}: {
  title: string;
  count: number;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-1.5 pt-3 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
        {title}
      </h3>
      {count > 0 && (
        <span className="text-xs text-text-tertiary">{count}</span>
      )}
    </div>
  );
}

function EmptySection() {
  return (
    <p className="py-2 text-xs italic text-text-tertiary">
      No data extracted yet.
    </p>
  );
}

function FactRow({
  fact,
  files,
  onConfirm,
}: {
  fact: CaseFactInfo;
  files: CaseFileInfo[];
  onConfirm: (factId: string) => void;
}) {
  const badge = confidenceBadge(fact.confidence);
  return (
    <div className="group flex items-start gap-2 rounded px-2 py-1.5 hover:bg-surface">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">
            {fact.fact_type.replace(/_/g, " ")}
          </span>
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
              badge === "high"
                ? "bg-green-100 text-green-700"
                : badge === "medium"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {Math.round(fact.confidence * 100)}%
          </span>
          <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-text-tertiary">
            {fact.extraction_method}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-text-secondary">
          {formatValue(fact.value)}
        </p>
        {fact.source_file_id && (
          <p className="mt-0.5 text-[10px] text-text-tertiary">
            Source: {sourceLabel(fact.source_file_id, files)}
          </p>
        )}
        {fact.effective_date && (
          <p className="mt-0.5 text-[10px] text-text-tertiary">
            Effective: {fact.effective_date}
          </p>
        )}
      </div>
      {fact.confirmed ? (
        <span
          className="mt-0.5 shrink-0 text-[10px] font-medium text-green-600"
          title="Confirmed"
        >
          Confirmed
        </span>
      ) : (
        <button
          onClick={() => onConfirm(fact.id)}
          className="mt-0.5 shrink-0 rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
          title="Confirm this fact"
        >
          Confirm
        </button>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function CaseInfo({ caseId, files, onClose }: CaseInfoProps) {
  const [context, setContext] = useState<CaseContextInfo | null>(null);
  const [facts, setFacts] = useState<CaseFactInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);
      const [ctx, factsResp] = await Promise.all([
        getCaseContext(caseId),
        listFacts(caseId),
      ]);
      setContext(ctx);
      setFacts(factsResp.facts);
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Failed to load case info"
      );
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleConfirm = useCallback(
    async (factId: string) => {
      try {
        const updated = await confirmFact(caseId, factId);
        setFacts((prev) =>
          prev.map((f) => (f.id === factId ? updated : f))
        );
      } catch {
        // Silently fail — fact may have been confirmed already
      }
    },
    [caseId]
  );

  // Group facts by category
  const factsByCategory = facts.reduce<Record<string, CaseFactInfo[]>>(
    (acc, f) => {
      const cat = f.category;
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(f);
      return acc;
    },
    {}
  );

  // Map category to display name
  const categoryLabels: Record<string, string> = {
    party: "Parties",
    employment: "Employment",
    claim: "Claims",
    date: "Key Dates",
    financial: "Financials",
    court: "Court",
    attorney: "Attorneys",
  };

  // Ordered section keys
  const sectionOrder = [
    "party",
    "court",
    "attorney",
    "employment",
    "claim",
    "date",
    "financial",
  ];

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <p className="text-sm text-text-tertiary">Loading case info...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background px-4">
        <div className="rounded-lg border border-error-border bg-error-bg px-6 py-4 text-center">
          <p className="text-sm text-error-text">{error}</p>
          <button
            onClick={onClose}
            className="mt-3 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col bg-background" data-testid="case-info-panel">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">
            Case Info
          </h2>
          <p className="text-xs text-text-tertiary">
            {context?.fact_count ?? 0} facts \u00b7{" "}
            {context?.confirmed_count ?? 0} confirmed
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-text-tertiary transition-colors hover:bg-surface hover:text-text-primary"
          title="Close case info"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {facts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-sm text-text-tertiary">
              No facts extracted yet.
            </p>
            <p className="mt-1 text-xs text-text-tertiary">
              Upload documents and the system will extract key facts
              automatically.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {sectionOrder.map((cat) => {
              const catFacts = factsByCategory[cat];
              return (
                <div key={cat}>
                  <SectionHeader
                    title={categoryLabels[cat] || cat}
                    count={catFacts?.length ?? 0}
                  />
                  {!catFacts || catFacts.length === 0 ? (
                    <EmptySection />
                  ) : (
                    <div className="mt-1 space-y-0.5">
                      {catFacts.map((fact) => (
                        <FactRow
                          key={fact.id}
                          fact={fact}
                          files={files}
                          onConfirm={handleConfirm}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Extraction sources */}
            {context?.extraction_sources &&
              Object.keys(context.extraction_sources).length > 0 && (
                <div>
                  <SectionHeader
                    title="Extraction Sources"
                    count={
                      Object.keys(context.extraction_sources).length
                    }
                  />
                  <div className="mt-1 space-y-1 px-2">
                    {Object.entries(context.extraction_sources).map(
                      ([fileId, methods]) => (
                        <div
                          key={fileId}
                          className="text-xs text-text-secondary"
                        >
                          <span className="font-medium">
                            {sourceLabel(fileId, files)}
                          </span>
                          <span className="ml-1 text-text-tertiary">
                            ({methods.join(", ")})
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
