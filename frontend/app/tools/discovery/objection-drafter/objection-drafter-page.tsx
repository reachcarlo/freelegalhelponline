"use client";

import { ObjectionDrafterProvider } from "@/lib/objection-context";
import ObjectionDrafter from "@/components/discovery/objection-drafter";

export default function ObjectionDrafterPage() {
  return (
    <ObjectionDrafterProvider>
      <ObjectionDrafter />
    </ObjectionDrafterProvider>
  );
}
