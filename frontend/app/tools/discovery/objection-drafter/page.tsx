import { Metadata } from "next";
import ObjectionDrafterPage from "./objection-drafter-page";

export const metadata: Metadata = {
  title: "Objection Drafter — California Employment Discovery",
  description:
    "AI-powered discovery objection drafter for California employment litigation. Paste discovery requests, get formatted objections with statutory and case law citations.",
};

export default function ObjectionDrafterRoute() {
  return <ObjectionDrafterPage />;
}
