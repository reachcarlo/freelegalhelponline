"use client";

import { use } from "react";
import DiscoveryWorkspaceWrapper from "../discovery-workspace-wrapper";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function RfasPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return (
    <DiscoveryWorkspaceWrapper caseId={caseId}>
      <DocxWizard
        toolType="rfas"
        title="Requests for Admission"
        toolLabel="RFAs"
        limit={35}
        limitType="fact"
        limitLabel="fact requests"
        caseId={caseId}
      />
    </DiscoveryWorkspaceWrapper>
  );
}
