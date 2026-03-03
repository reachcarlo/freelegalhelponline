import { Metadata } from "next";
import FrogWizardPage from "./frog-wizard-page";

export const metadata: Metadata = {
  title: "Form Interrogatories — General (DISC-001)",
  description:
    "Generate Judicial Council Form DISC-001 for California employment cases. Select sections, enter case info, and download editable PDFs.",
};

export default function FrogsGeneralPage() {
  return <FrogWizardPage />;
}
