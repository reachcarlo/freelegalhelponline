import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Legal Tools — California Employment Rights",
  description:
    "Free interactive tools for California employment law. Calculate statute of limitations deadlines, filing dates, and more.",
};

const tools = [
  {
    href: "/tools/guided-intake",
    title: "Guided Intake & Rights Summary",
    description:
      "Not sure where to start? Answer a few simple questions to identify your employment issue, get a personalized AI-generated summary of your rights, and find the right tools.",
  },
  {
    href: "/tools/deadline-calculator",
    title: "Statute of Limitations Calculator",
    description:
      "Enter your claim type and incident date to see all relevant filing deadlines with urgency warnings.",
  },
  {
    href: "/tools/agency-routing",
    title: "Agency Routing Guide",
    description:
      "Find out which California government agency handles your employment complaint and how to file.",
  },
  {
    href: "/tools/unpaid-wages-calculator",
    title: "Unpaid Wages Calculator",
    description:
      "Estimate how much you're owed including unpaid wages, waiting time penalties, and meal/rest break premiums.",
  },
  {
    href: "/tools/incident-docs",
    title: "Incident Documentation Helper",
    description:
      "Document workplace incidents while details are fresh. Guided forms, evidence checklists, and exportable records. Your data stays in your browser.",
  },
];

export default function ToolsIndex() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <span className="text-text-primary">Tools</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Legal Tools
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Free interactive tools to help you understand your California
          employment rights.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {tools.map((tool, i) => (
            <Link
              key={tool.href}
              href={tool.href}
              className={
                i === 0
                  ? "rounded-lg border border-border border-l-4 border-l-accent p-5 transition-colors hover:border-border-hover hover:bg-accent-surface sm:col-span-2"
                  : "rounded-lg border border-border p-5 transition-colors hover:border-border-hover hover:bg-accent-surface"
              }
            >
              {i === 0 && (
                <p className="text-xs font-medium text-accent mb-1">
                  Recommended starting point
                </p>
              )}
              <h2 className="font-semibold text-text-primary">{tool.title}</h2>
              <p className="mt-2 text-sm text-text-tertiary">
                {tool.description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
