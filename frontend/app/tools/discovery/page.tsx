import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Discovery Tools — California Employment Law",
  description:
    "Generate California employment law discovery documents. Form Interrogatories (DISC-001, DISC-002), Special Interrogatories, Requests for Production, Requests for Admission.",
};

const tools = [
  {
    href: "/tools/discovery/frogs-general",
    key: "frogs_general",
    title: "Form Interrogatories — General (DISC-001)",
    description:
      "Select and generate Judicial Council Form DISC-001 with pre-populated case information. 17 section groups covering identity, insurance, damages, medical, and more.",
    format: "PDF",
  },
  {
    href: "/tools/discovery/frogs-employment",
    key: "frogs_employment",
    title: "Form Interrogatories — Employment (DISC-002)",
    description:
      "Select and generate Judicial Council Form DISC-002 covering employment relationship, termination, discrimination, harassment, retaliation, and whistleblower claims.",
    format: "PDF",
  },
  {
    href: "/tools/discovery/srogs",
    key: "srogs",
    title: "Special Interrogatories (SROGs)",
    description:
      "Build custom special interrogatories from curated question banks organized by claim type. Includes 35-interrogatory limit tracking per CCP 2030.030.",
    format: "Word",
  },
  {
    href: "/tools/discovery/rfpds",
    key: "rfpds",
    title: "Requests for Production of Documents (RFPDs)",
    description:
      "Generate document production requests tailored to your employment claims. Includes standard definitions and production instructions.",
    format: "Word",
  },
  {
    href: "/tools/discovery/rfas",
    key: "rfas",
    title: "Requests for Admission (RFAs)",
    description:
      "Draft requests for admission with separate tracking for fact-based (35 limit per CCP 2033.030) and genuineness-of-document requests (unlimited).",
    format: "Word",
  },
];

export default function DiscoveryToolsIndex() {
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
          <span className="text-text-primary">Discovery</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Discovery Document Generator
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Generate California employment law discovery documents. Select a tool
          below to start building your discovery set.
        </p>

        <div className="mt-8 space-y-4">
          {tools.map((tool) => (
            <Link
              key={tool.key}
              href={tool.href}
              className="block rounded-lg border border-border p-5 transition-colors hover:border-border-hover hover:bg-accent-surface"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-semibold text-text-primary">
                    {tool.title}
                  </h2>
                  <p className="mt-2 text-sm text-text-tertiary">
                    {tool.description}
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium text-text-secondary">
                  {tool.format}
                </span>
              </div>
            </Link>
          ))}
        </div>

        <p className="mt-8 rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
          These tools generate discovery documents based on your selections.
          They do not constitute legal advice. Generated documents should be
          reviewed by a licensed California attorney before filing.
        </p>
      </div>
    </div>
  );
}
