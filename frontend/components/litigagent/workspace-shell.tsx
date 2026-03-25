"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  CaseContextInfo,
  CaseInfo,
  getCase,
  getCaseContext,
} from "@/lib/litigagent-api";
import WorkspaceSidebar, { WorkspaceBottomBar } from "./workspace-sidebar";
import CommandPalette from "./command-palette";

/** Map URL segment → breadcrumb label */
const TOOL_LABELS: Record<string, string> = {
  files: "Files",
  chat: "Chat",
  info: "Info",
  discovery: "Discovery",
  objections: "Objections",
  demand: "Demand",
  timeline: "Timeline",
  analysis: "Analysis",
  // Discovery sub-routes
  srogs: "SROGs",
  rfpds: "RFPDs",
  rfas: "RFAs",
  "frogs-general": "FROGs General",
  "frogs-employment": "FROGs Employment",
  "objection-drafter": "Objection Drafter",
};

interface WorkspaceShellProps {
  caseId: string;
  children: React.ReactNode;
}

/** Chevron separator for breadcrumb */
function ChevronSeparator() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-text-tertiary"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
  );
}

/**
 * Breadcrumb: Cases > Case Name > Tool
 *
 * Derives the current tool from the URL pathname.
 * All segments except the last are clickable links.
 */
function Breadcrumb({
  caseId,
  caseName,
}: {
  caseId: string;
  caseName: string;
}) {
  const pathname = usePathname();
  const basePath = `/cases/${caseId}`;

  // Extract segments after /cases/[caseId]/
  const afterBase = pathname.replace(basePath, "").replace(/^\//, "");
  const segments = afterBase ? afterBase.split("/").filter(Boolean) : [];

  // Build breadcrumb items: Cases > Case Name > Tool [> Sub-tool]
  const crumbs: { label: string; href?: string }[] = [
    { label: "Cases", href: "/cases" },
    {
      label: caseName,
      href: segments.length > 0 ? `${basePath}/files` : undefined,
    },
  ];

  // Add tool segments (e.g., "files", "discovery/srogs" → "Discovery" > "SROGs")
  segments.forEach((seg, i) => {
    const label = TOOL_LABELS[seg] ?? seg.charAt(0).toUpperCase() + seg.slice(1);
    const isLast = i === segments.length - 1;
    crumbs.push({
      label,
      href: isLast
        ? undefined
        : `${basePath}/${segments.slice(0, i + 1).join("/")}`,
    });
  });

  return (
    <nav
      className="flex items-center gap-1.5 min-w-0 text-sm"
      aria-label="Breadcrumb"
      data-testid="workspace-breadcrumb"
    >
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1.5 min-w-0">
          {i > 0 && <ChevronSeparator />}
          {crumb.href ? (
            <Link
              href={crumb.href}
              className="shrink-0 text-text-tertiary transition-colors hover:text-accent"
              data-testid={i === 1 ? "case-name" : undefined}
            >
              {crumb.label}
            </Link>
          ) : (
            <span
              className="truncate font-medium text-text-primary"
              data-testid={i === 1 ? "case-name" : undefined}
            >
              {crumb.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
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
          <Link
            href="/cases"
            className="mt-3 inline-block rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface"
          >
            Back to Cases
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" data-testid="workspace-shell">
      <CommandPalette caseId={caseId} />

      {/* Case header with breadcrumb */}
      <div
        className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5"
        data-testid="workspace-header"
      >
        <Breadcrumb caseId={caseId} caseName={caseInfo?.name ?? ""} />

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
