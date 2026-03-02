import { Metadata } from "next";
import Link from "next/link";
import DeadlineCalculator from "@/components/deadline-calculator";

export const metadata: Metadata = {
  title: "Statute of Limitations Calculator — California Employment Law",
  description:
    "Calculate filing deadlines for California employment claims. Enter your claim type and incident date to see all relevant statutes of limitations with urgency warnings.",
  openGraph: {
    title: "Statute of Limitations Calculator — California Employment Law",
    description:
      "Calculate filing deadlines for California employment claims including FEHA, wage theft, wrongful termination, and more.",
    type: "website",
  },
};

export default function DeadlineCalculatorPage() {
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
          <span className="text-text-primary">Deadline Calculator</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Statute of Limitations Calculator
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Select your claim type and the date of the incident to see all
          relevant filing deadlines.
        </p>

        <div className="mt-8">
          <DeadlineCalculator />
        </div>

        <div className="mt-8 rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
          <strong>Important:</strong> These deadlines are general estimates
          based on California law. Actual deadlines may vary depending on
          tolling, discovery rules, continuing violations, or other legal
          doctrines. Consult a licensed California employment attorney for
          advice about your specific situation.
        </div>
      </div>
    </div>
  );
}
