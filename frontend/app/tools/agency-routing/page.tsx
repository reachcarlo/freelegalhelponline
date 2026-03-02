import { Metadata } from "next";
import Link from "next/link";
import AgencyRouting from "@/components/agency-routing";

export const metadata: Metadata = {
  title: "Agency Routing Guide — California Employment Law",
  description:
    "Find out which California government agency handles your employment complaint. Get filing instructions, portal links, and process overviews for DLSE, CRD, EDD, Cal/OSHA, and more.",
  openGraph: {
    title: "Agency Routing Guide — California Employment Law",
    description:
      "Find out which California government agency handles your employment complaint and how to file.",
    type: "website",
  },
};

export default function AgencyRoutingPage() {
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
          <span className="text-text-primary">Agency Routing Guide</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Agency Routing Guide
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Select your employment issue to find out which California government
          agency handles your complaint, how to file, and what to expect.
        </p>

        <div className="mt-8">
          <AgencyRouting />
        </div>

        <div className="mt-8 rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
          <strong>Important:</strong> This routing guide provides general
          information about California government agencies that handle employment
          complaints. It is not legal advice. Filing requirements, deadlines, and
          procedures may vary depending on your specific situation. Consult a
          licensed California employment attorney for advice about your specific
          situation.
        </div>
      </div>
    </div>
  );
}
