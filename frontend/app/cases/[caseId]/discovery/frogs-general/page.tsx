"use client";

import { use } from "react";
import DiscoveryWorkspaceWrapper from "../discovery-workspace-wrapper";
import FrogWizard from "@/components/discovery/frog-wizard";

export default function FrogsGeneralPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return (
    <DiscoveryWorkspaceWrapper caseId={caseId}>
      <FrogWizard
        toolType="frogs_general"
        title="Form Interrogatories — General"
        formLabel="DISC-001"
        caseId={caseId}
      />
    </DiscoveryWorkspaceWrapper>
  );
}
