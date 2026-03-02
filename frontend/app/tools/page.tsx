import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Legal Tools — California Employment Rights",
  description:
    "Free interactive tools for California employment law. Calculate statute of limitations deadlines, filing dates, and more.",
};

const tools = [
  {
    href: "/tools/deadline-calculator",
    title: "Statute of Limitations Calculator",
    description:
      "Enter your claim type and incident date to see all relevant filing deadlines with urgency warnings.",
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
          {tools.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="rounded-lg border border-border p-5 transition-colors hover:border-border-hover hover:bg-accent-surface"
            >
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
