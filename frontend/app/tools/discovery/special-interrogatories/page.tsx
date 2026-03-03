import { Metadata } from "next";
import SrogWizardPage from "./srog-wizard-page";

export const metadata: Metadata = {
  title: "Special Interrogatories (SROGs) — California Employment Law",
  description:
    "Build special interrogatories from curated employment law question banks. 35-limit tracking per CCP 2030.030, inline editing, and Word document generation.",
};

export default function SpecialInterrogatoriesPage() {
  return <SrogWizardPage />;
}
