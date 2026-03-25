"use client";

import { use } from "react";
import { ObjectionDrafterProvider } from "@/lib/objection-context";
import ObjectionDrafter from "@/components/discovery/objection-drafter";

/**
 * Objection Drafter does not use DiscoveryProvider — it has its own context.
 * No CaseContext auto-fill needed here.
 */
export default function ObjectionDrafterPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  use(params); // consume params to avoid Next.js warning
  return (
    <ObjectionDrafterProvider>
      <ObjectionDrafter />
    </ObjectionDrafterProvider>
  );
}
