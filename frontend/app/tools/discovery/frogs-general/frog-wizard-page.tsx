"use client";

import { DiscoveryProvider } from "@/lib/discovery-context";
import FrogWizard from "@/components/discovery/frog-wizard";

export default function FrogWizardPage() {
  return (
    <DiscoveryProvider>
      <FrogWizard
        toolType="frogs_general"
        title="Form Interrogatories — General"
        formLabel="DISC-001"
      />
    </DiscoveryProvider>
  );
}
