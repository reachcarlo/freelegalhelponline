"use client";

import { use } from "react";
import DiscoveryWorkspaceWrapper from "../discovery-workspace-wrapper";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function RfpdsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return (
    <DiscoveryWorkspaceWrapper caseId={caseId}>
      <DocxWizard
        toolType="rfpds"
        title="Requests for Production of Documents"
        toolLabel="RFPDs"
        limit={null}
        showProductionInstructions
        caseId={caseId}
      />
    </DiscoveryWorkspaceWrapper>
  );
}
