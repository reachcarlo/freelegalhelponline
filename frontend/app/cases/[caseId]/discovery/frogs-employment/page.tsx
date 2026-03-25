"use client";

import { use } from "react";
import DiscoveryWorkspaceWrapper from "../discovery-workspace-wrapper";
import FrogWizard from "@/components/discovery/frog-wizard";

export default function FrogsEmploymentPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return (
    <DiscoveryWorkspaceWrapper caseId={caseId}>
      <FrogWizard
        toolType="frogs_employment"
        title="Form Interrogatories — Employment"
        formLabel="DISC-002"
        caseId={caseId}
      />
    </DiscoveryWorkspaceWrapper>
  );
}
