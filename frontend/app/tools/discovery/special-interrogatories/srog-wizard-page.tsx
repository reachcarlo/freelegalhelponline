"use client";

import { DiscoveryProvider } from "@/lib/discovery-context";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function SrogWizardPage() {
  return (
    <DiscoveryProvider>
      <DocxWizard
        toolType="srogs"
        title="Special Interrogatories"
        toolLabel="SROGs"
        limit={35}
        limitLabel="interrogatories"
      />
    </DiscoveryProvider>
  );
}
