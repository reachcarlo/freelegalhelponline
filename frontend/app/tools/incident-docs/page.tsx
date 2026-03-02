import { Metadata } from "next";
import Link from "next/link";
import IncidentDocs from "@/components/incident-docs";

export const metadata: Metadata = {
  title: "Incident Documentation Helper — California Employment Law",
  description:
    "Document workplace incidents while details are fresh. Guided forms, evidence checklists, and exportable personal records. Your data stays in your browser.",
  openGraph: {
    title: "Incident Documentation Helper — California Employment Law",
    description:
      "Document workplace incidents with guided forms, evidence checklists, and exportable records. Privacy-first: your data stays in your browser.",
    type: "website",
  },
};

export default function IncidentDocsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <Link href="/tools" className="hover:text-accent">
            Tools
          </Link>
          {" / "}
          <span className="text-text-primary">Incident Documentation</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Incident Documentation Helper
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Document workplace incidents while details are fresh. Guided forms
          help you capture the right information for your type of incident.
        </p>

        {/* Privacy badge */}
        <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-accent bg-accent-surface px-3 py-1.5 text-sm text-accent">
          <svg
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
          Privacy-first: your data stays in your browser
        </div>

        <div className="mt-8">
          <IncidentDocs />
        </div>

        <div className="mt-8 rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
          <strong>Important:</strong> This tool helps you create a personal
          record of workplace incidents. It is NOT a legal document and does not
          constitute legal advice. Your data is stored only in your browser and
          is never sent to our servers. Consult a licensed California employment
          attorney for advice about your specific situation.
        </div>
      </div>
    </div>
  );
}
