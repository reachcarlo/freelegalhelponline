"use client";

import { use, useCallback, useEffect, useState } from "react";
import { ObjectionDrafterProvider, useObjectionDrafter } from "@/lib/objection-context";
import ObjectionDrafter from "@/components/discovery/objection-drafter";
import {
  getCaseContext,
  getFile,
  listFacts,
  listFiles,
  type CaseContextInfo,
  type CaseFactInfo,
  type CaseFileInfo,
} from "@/lib/litigagent-api";
import { useAuth } from "@/lib/auth-context";

/**
 * Workspace objection drafter route — `/cases/[caseId]/objections`.
 *
 * Fetches CaseContext and passes it to ObjectionDrafterProvider for
 * party role inference (V2.5.2). Detects discovery_request facts in
 * case files and offers to pre-populate the drafter (V2.5.3).
 */
export default function ObjectionsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  const { user } = useAuth();
  const [caseContext, setCaseContext] = useState<CaseContextInfo | undefined>();

  useEffect(() => {
    let cancelled = false;
    getCaseContext(caseId)
      .then((ctx) => {
        if (!cancelled) setCaseContext(ctx);
      })
      .catch(() => {
        /* best-effort */
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  return (
    <ObjectionDrafterProvider caseContext={caseContext} userEmail={user?.email} caseId={caseId}>
      <DiscoveryRequestDetector caseId={caseId} />
      <ObjectionDrafter />
    </ObjectionDrafterProvider>
  );
}

// ── V2.5.3: Discovery request detection ──────────────────────────────

interface DetectedFile {
  fileId: string;
  filename: string;
}

function DiscoveryRequestDetector({ caseId }: { caseId: string }) {
  const { state, dispatch } = useObjectionDrafter();
  const [detectedFiles, setDetectedFiles] = useState<DetectedFile[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [factsResult, files] = await Promise.all([
          listFacts(caseId),
          listFiles(caseId),
        ]);
        if (cancelled) return;

        // Find facts with fact_type="discovery_request" that have a source file
        const discoveryFacts = factsResult.facts.filter(
          (f: CaseFactInfo) =>
            f.fact_type === "discovery_request" && f.source_file_id
        );
        if (discoveryFacts.length === 0) return;

        // Build file ID → filename map
        const fileMap = new Map<string, string>();
        for (const file of files) {
          fileMap.set(file.id, file.original_filename);
        }

        // Deduplicate by source_file_id
        const seen = new Set<string>();
        const detected: DetectedFile[] = [];
        for (const fact of discoveryFacts) {
          const fid = fact.source_file_id!;
          if (seen.has(fid)) continue;
          seen.add(fid);
          detected.push({
            fileId: fid,
            filename: fileMap.get(fid) || "Unknown file",
          });
        }
        if (!cancelled) setDetectedFiles(detected);
      } catch {
        /* best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const handleUseFile = useCallback(
    async (fileId: string) => {
      setLoading(fileId);
      try {
        const detail = await getFile(caseId, fileId);
        const text = detail.edited_text || detail.extracted_text || "";
        if (!text.trim()) {
          setLoading(null);
          return;
        }
        dispatch({ type: "SET_RAW_TEXT", text });
        dispatch({ type: "SET_STEP", step: 1 });
        setDismissed(true);
      } catch {
        /* best-effort */
      } finally {
        setLoading(null);
      }
    },
    [caseId, dispatch]
  );

  // Hide banner if dismissed, no detected files, or user already has input
  if (
    dismissed ||
    detectedFiles.length === 0 ||
    state.rawText.trim().length > 0 ||
    state.currentStep > 1
  ) {
    return null;
  }

  return (
    <div
      className="mx-auto max-w-2xl px-4 pt-4 sm:px-6"
      data-testid="discovery-request-banner"
    >
      <div className="rounded-lg border border-accent/30 bg-accent/5 px-4 py-3">
        <p className="mb-2 text-sm font-medium text-text-primary">
          Discovery requests detected in your files
        </p>
        <div className="flex flex-wrap gap-2">
          {detectedFiles.map((df) => (
            <button
              key={df.fileId}
              type="button"
              disabled={loading !== null}
              onClick={() => handleUseFile(df.fileId)}
              className="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-white px-3 py-1.5 text-sm text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
              data-testid={`use-file-${df.fileId}`}
            >
              {loading === df.fileId ? (
                <span className="flex items-center gap-1.5">
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Loading…
                </span>
              ) : (
                <>Draft objections to {df.filename}?</>
              )}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="mt-2 text-xs text-text-tertiary hover:text-text-secondary"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
