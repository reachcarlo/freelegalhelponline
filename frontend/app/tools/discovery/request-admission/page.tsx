import { Metadata } from "next";
import RfaWizardPage from "./rfa-wizard-page";

export const metadata: Metadata = {
  title: "Requests for Admission (RFAs) — California Employment Law",
  description:
    "Draft requests for admission with separate tracking for fact-based (35 limit per CCP 2033.030) and genuineness-of-document requests (unlimited).",
};

export default function RequestAdmissionPage() {
  return <RfaWizardPage />;
}
