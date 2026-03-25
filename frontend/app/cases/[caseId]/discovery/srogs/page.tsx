"use client";

import { use } from "react";
import DiscoveryWorkspaceWrapper from "../discovery-workspace-wrapper";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function SrogsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return (
    <DiscoveryWorkspaceWrapper caseId={caseId}>
      <DocxWizard
        toolType="srogs"
        title="Special Interrogatories"
        toolLabel="SROGs"
        limit={35}
        limitLabel="interrogatories"
        caseId={caseId}
      />
    </DiscoveryWorkspaceWrapper>
  );
}
