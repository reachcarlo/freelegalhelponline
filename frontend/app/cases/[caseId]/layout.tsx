"use client";

import { use } from "react";
import WorkspaceShell from "@/components/litigagent/workspace-shell";
import { WorkspaceProvider } from "@/lib/workspace-context";

/**
 * Workspace shell layout for /cases/[caseId]/*.
 *
 * Wraps all child routes in the persistent workspace chrome
 * (case header + sidebar + tool canvas).
 * WorkspaceProvider preserves per-tool state across route transitions.
 */
export default function CaseWorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);

  return (
    <WorkspaceProvider caseId={caseId}>
      <WorkspaceShell caseId={caseId}>{children}</WorkspaceShell>
    </WorkspaceProvider>
  );
}
