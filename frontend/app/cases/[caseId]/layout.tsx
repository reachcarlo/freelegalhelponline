"use client";

import { use } from "react";
import WorkspaceShell from "@/components/litigagent/workspace-shell";

/**
 * Workspace shell layout for /cases/[caseId]/*.
 *
 * Wraps all child routes in the persistent workspace chrome
 * (case header + sidebar + tool canvas).
 */
export default function CaseWorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);

  return <WorkspaceShell caseId={caseId}>{children}</WorkspaceShell>;
}
