"use client";

import { use } from "react";
import CaseLayout from "@/components/litigagent/case-layout";

/**
 * Files view — renders the existing three-panel layout (files + text + notes).
 *
 * showHeader=false because the workspace shell (layout.tsx) provides
 * the case header.
 */
export default function FilesPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return <CaseLayout caseId={caseId} showHeader={false} />;
}
