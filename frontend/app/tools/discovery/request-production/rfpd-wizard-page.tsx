"use client";

import { DiscoveryProvider } from "@/lib/discovery-context";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function RfpdWizardPage() {
  return (
    <DiscoveryProvider>
      <DocxWizard
        toolType="rfpds"
        title="Requests for Production of Documents"
        toolLabel="RFPDs"
        limit={null}
        showProductionInstructions
      />
    </DiscoveryProvider>
  );
}
