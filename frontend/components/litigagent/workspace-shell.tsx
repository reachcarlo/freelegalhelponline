"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CaseContextInfo,
  CaseInfo,
  getCase,
  getCaseContext,
} from "@/lib/litigagent-api";
import WorkspaceSidebar, { WorkspaceBottomBar } from "./workspace-sidebar";

interface WorkspaceShellProps {
  caseId: string;
  children: React.ReactNode;
}

/**
 * Workspace shell: persistent chrome around the tool canvas.
 *
 * Renders the case header (back link + case name) and a sidebar
 * placeholder (populated in V2.3a.3). Children render in the
 * tool canvas area.
 */
export default function WorkspaceShell({
  caseId,
  children,
}: WorkspaceShellProps) {
  const router = useRouter();
  const [caseInfo, setCaseInfo] = useState<CaseInfo | null>(null);
  const [context, setContext] = useState<CaseContextInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCase = useCallback(async () => {
    try {
      setError(null);
      const [c, ctx] = await Promise.all([
        getCase(caseId),
        getCaseContext(caseId).catch(() => null),
      ]);
      setCaseInfo(c);
      setContext(ctx);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load case");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-background">
        <p className="text-text-tertiary">Loading case...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background px-4">
        <div className="rounded-lg border border-error-border bg-error-bg px-6 py-4 text-center">
          <p className="text-sm text-error-text">{error}</p>
          <button
            onClick={() => router.push("/cases")}
            className="mt-3 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface"
          >
            Back to Cases
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" data-testid="workspace-shell">
      {/* Case header */}
      <div
        className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5"
        data-testid="workspace-header"
      >
        <div className="flex items-center min-w-0">
          <button
            onClick={() => router.push("/cases")}
            className="flex items-center gap-1 rounded px-2 py-1 text-sm text-text-tertiary transition-colors hover:bg-accent-surface hover:text-accent shrink-0"
            data-testid="back-to-cases"
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
                d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
              />
            </svg>
            Cases
          </button>
          <span className="mx-3 text-border shrink-0">|</span>
          <div className="min-w-0">
            <h1
              className="text-sm font-semibold text-text-primary truncate"
              data-testid="case-name"
            >
              {caseInfo?.name}
            </h1>
            {caseInfo?.description && (
              <p
                className="text-xs text-text-tertiary truncate"
                data-testid="case-description"
              >
                {caseInfo.description}
              </p>
            )}
          </div>
        </div>

        {/* Fact count indicator */}
        {context && context.fact_count > 0 && (
          <div
            className="flex items-center gap-1.5 rounded-md bg-accent/10 px-2.5 py-1 text-xs shrink-0 ml-3"
            data-testid="fact-count-indicator"
            title={`${context.confirmed_count} of ${context.fact_count} facts confirmed`}
          >
            <svg
              className="h-3.5 w-3.5 text-accent"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-accent font-medium">
              {context.confirmed_count}/{context.fact_count}
            </span>
            <span className="text-text-tertiary hidden sm:inline">facts</span>
          </div>
        )}
      </div>

      {/* Body: sidebar + tool canvas */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar navigation */}
        <aside className="hidden w-14 shrink-0 md:block lg:w-48">
          <WorkspaceSidebar
            caseId={caseId}
            badges={{ files: caseInfo?.file_count ?? 0 }}
          />
        </aside>

        {/* Tool canvas */}
        <div className="flex flex-1 flex-col min-w-0" data-testid="workspace-canvas">
          {children}
        </div>
      </div>

      {/* Bottom tab bar — mobile only */}
      <div className="md:hidden">
        <WorkspaceBottomBar
          caseId={caseId}
          badges={{ files: caseInfo?.file_count ?? 0 }}
        />
      </div>
    </div>
  );
}
