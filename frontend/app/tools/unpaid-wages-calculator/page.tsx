import { Metadata } from "next";
import Link from "next/link";
import UnpaidWagesCalculator from "@/components/unpaid-wages-calculator";

export const metadata: Metadata = {
  title: "Unpaid Wages Calculator — California Employment Law",
  description:
    "Estimate how much you're owed under California labor law. Calculate unpaid wages, waiting time penalties (Lab. Code §203), meal/rest break premiums, and prejudgment interest.",
  openGraph: {
    title: "Unpaid Wages Calculator — California Employment Law",
    description:
      "Estimate how much you're owed including unpaid wages, waiting time penalties, and meal/rest break premiums.",
    type: "website",
  },
};

export default function UnpaidWagesCalculatorPage() {
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
          <span className="text-text-primary">Unpaid Wages Calculator</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Unpaid Wages Calculator
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Estimate how much you may be owed under California labor law, including
          unpaid wages, waiting time penalties, meal and rest break premiums, and
          prejudgment interest.
        </p>

        <div className="mt-8">
          <UnpaidWagesCalculator />
        </div>

        <div className="mt-8 rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
          <strong>Important:</strong> This calculator provides general estimates
          based on California labor law. Actual amounts may vary depending on
          your specific employment agreement, applicable exemptions, collective
          bargaining agreements, overtime rates, and other factors. Waiting time
          penalties and interest calculations are simplified estimates. Consult a
          licensed California employment attorney for advice about your specific
          situation.
        </div>
      </div>
    </div>
  );
}
