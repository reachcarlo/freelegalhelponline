"use client";

import { use } from "react";
import CaseLayout from "@/components/litigagent/case-layout";

/**
 * Default case workspace view — renders the existing three-panel layout.
 *
 * showHeader=false because the workspace shell (layout.tsx) provides
 * the case header. V2.3b.1 will migrate this to /cases/[caseId]/files.
 */
export default function CaseWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return <CaseLayout caseId={caseId} showHeader={false} />;
}
