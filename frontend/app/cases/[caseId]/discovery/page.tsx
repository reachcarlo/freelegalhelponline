"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  listArtifacts,
  deleteArtifact,
  type ArtifactInfo,
} from "@/lib/litigagent-api";

/**
 * Discovery hub — lists available discovery tools inside the case workspace.
 *
 * Links navigate to sub-routes within the workspace (e.g. /cases/[id]/discovery/srogs).
 * Displays previously generated artifacts at the top when present.
 */

interface DiscoveryTool {
  key: string;
  title: string;
  description: string;
  segment: string;
  format: string;
}

const TOOLS: DiscoveryTool[] = [
  {
    key: "objection_drafter",
    title: "Objection Drafter",
    description:
      "AI-powered objection drafter. Paste discovery requests, get formatted objections with strength ratings, statutory and case law citations.",
    segment: "objection-drafter",
    format: "AI",
  },
  {
    key: "frogs_general",
    title: "Form Interrogatories — General (DISC-001)",
    description:
      "Select and generate Judicial Council Form DISC-001 with pre-populated case information. 17 section groups covering identity, insurance, damages, medical, and more.",
    segment: "frogs-general",
    format: "PDF",
  },
  {
    key: "frogs_employment",
    title: "Form Interrogatories — Employment (DISC-002)",
    description:
      "Select and generate Judicial Council Form DISC-002 covering employment relationship, termination, discrimination, harassment, retaliation, and whistleblower claims.",
    segment: "frogs-employment",
    format: "PDF",
  },
  {
    key: "srogs",
    title: "Special Interrogatories (SROGs)",
    description:
      "Build custom special interrogatories from curated question banks organized by claim type. Includes 35-interrogatory limit tracking per CCP 2030.030.",
    segment: "srogs",
    format: "Word",
  },
  {
    key: "rfpds",
    title: "Requests for Production of Documents (RFPDs)",
    description:
      "Generate document production requests tailored to your employment claims. Includes standard definitions and production instructions.",
    segment: "rfpds",
    format: "Word",
  },
  {
    key: "rfas",
    title: "Requests for Admission (RFAs)",
    description:
      "Draft requests for admission with separate tracking for fact-based (35 limit per CCP 2033.030) and genuineness-of-document requests (unlimited).",
    segment: "rfas",
    format: "Word",
  },
];

/** Map tool_source values to human-readable labels. */
const TOOL_LABELS: Record<string, string> = {
  srogs: "SROGs",
  rfpds: "RFPDs",
  rfas: "RFAs",
  frogs_general: "FROGs General",
  frogs_employment: "FROGs Employment",
  objection_drafter: "Objection Drafter",
};

/** Map tool_source to the hub sub-route segment. */
const TOOL_SEGMENTS: Record<string, string> = {
  srogs: "srogs",
  rfpds: "rfpds",
  rfas: "rfas",
  frogs_general: "frogs-general",
  frogs_employment: "frogs-employment",
  objection_drafter: "objection-drafter",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function DiscoveryHubPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  const basePath = `/cases/${caseId}/discovery`;

  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listArtifacts(caseId)
      .then((data) => {
        if (!cancelled) setArtifacts(data);
      })
      .catch(() => {
        /* best-effort */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const handleDelete = useCallback(
    async (artifactId: string) => {
      setDeletingId(artifactId);
      try {
        await deleteArtifact(caseId, artifactId);
        setArtifacts((prev) => prev.filter((a) => a.id !== artifactId));
      } catch {
        /* best-effort */
      } finally {
        setDeletingId(null);
      }
    },
    [caseId],
  );

  return (
    <div className="h-full overflow-y-auto" data-testid="discovery-hub">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          Discovery Tools
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          Generate discovery documents for this case. Select a tool below.
        </p>

        {/* Generated Artifacts */}
        {!loading && artifacts.length > 0 && (
          <section className="mt-6" data-testid="artifacts-section">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
              Generated Documents
            </h2>
            <ul className="mt-2 space-y-2">
              {artifacts.map((artifact) => {
                const label =
                  TOOL_LABELS[artifact.tool_source] || artifact.tool_source;
                const segment = TOOL_SEGMENTS[artifact.tool_source];
                return (
                  <li
                    key={artifact.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                    data-testid="artifact-item"
                  >
                    <div className="min-w-0">
                      <span className="font-medium text-text-primary">
                        {label}
                      </span>
                      {artifact.summary && (
                        <span className="ml-2 text-sm text-text-tertiary">
                          — {artifact.summary}
                        </span>
                      )}
                      <span className="ml-2 text-xs text-text-tertiary">
                        {formatDate(artifact.created_at)}
                      </span>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {segment && (
                        <Link
                          href={`${basePath}/${segment}`}
                          className="rounded px-2 py-1 text-xs font-medium text-accent hover:bg-accent-surface"
                        >
                          Open tool
                        </Link>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(artifact.id)}
                        disabled={deletingId === artifact.id}
                        className="rounded px-2 py-1 text-xs text-text-tertiary hover:text-red-600 disabled:opacity-50"
                        aria-label={`Delete ${label} artifact`}
                        data-testid="artifact-delete"
                      >
                        {deletingId === artifact.id ? "…" : "Delete"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <div className="mt-6 space-y-3">
          {TOOLS.map((tool) => (
            <Link
              key={tool.key}
              href={`${basePath}/${tool.segment}`}
              className="block rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface focus:outline-none focus:ring-2 focus:ring-accent/40"
              data-testid={`discovery-tool-${tool.key}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-semibold text-text-primary">
                    {tool.title}
                  </h2>
                  <p className="mt-1.5 text-sm text-text-tertiary">
                    {tool.description}
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium text-text-secondary">
                  {tool.format}
                </span>
              </div>
            </Link>
          ))}
        </div>

        <p className="mt-6 rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
          These tools generate discovery documents based on your selections.
          They do not constitute legal advice. Generated documents should be
          reviewed by a licensed California attorney before filing.
        </p>
      </div>
    </div>
  );
}
