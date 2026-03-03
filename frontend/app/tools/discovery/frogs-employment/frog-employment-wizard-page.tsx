"use client";

import { DiscoveryProvider } from "@/lib/discovery-context";
import FrogWizard from "@/components/discovery/frog-wizard";

export default function FrogEmploymentWizardPage() {
  return (
    <DiscoveryProvider>
      <FrogWizard
        toolType="frogs_employment"
        title="Form Interrogatories — Employment"
        formLabel="DISC-002"
      />
    </DiscoveryProvider>
  );
}
