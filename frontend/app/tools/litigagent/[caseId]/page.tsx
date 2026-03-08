"use client";

import { use } from "react";
import CaseLayout from "@/components/litigagent/case-layout";

export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return <CaseLayout caseId={caseId} />;
}
