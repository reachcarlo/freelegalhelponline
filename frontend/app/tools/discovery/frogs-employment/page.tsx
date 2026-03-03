import { Metadata } from "next";
import FrogEmploymentWizardPage from "./frog-employment-wizard-page";

export const metadata: Metadata = {
  title: "Form Interrogatories — Employment (DISC-002)",
  description:
    "Generate Judicial Council Form DISC-002 for California employment cases. Directional filtering for plaintiff/defendant, claim-based section suggestions.",
};

export default function FrogsEmploymentPage() {
  return <FrogEmploymentWizardPage />;
}
