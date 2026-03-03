"use client";

import { DiscoveryProvider } from "@/lib/discovery-context";
import DocxWizard from "@/components/discovery/docx-wizard";

export default function RfaWizardPage() {
  return (
    <DiscoveryProvider>
      <DocxWizard
        toolType="rfas"
        title="Requests for Admission"
        toolLabel="RFAs"
        limit={35}
        limitType="fact"
        limitLabel="fact requests"
      />
    </DiscoveryProvider>
  );
}
