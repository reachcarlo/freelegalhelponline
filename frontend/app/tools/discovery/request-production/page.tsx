import { Metadata } from "next";
import RfpdWizardPage from "./rfpd-wizard-page";

export const metadata: Metadata = {
  title: "Requests for Production of Documents (RFPDs) — California Employment Law",
  description:
    "Generate document production requests for California employment cases. Includes standard definitions and production instructions. Word document output.",
};

export default function RequestProductionPage() {
  return <RfpdWizardPage />;
}
