import { Metadata } from "next";
import Link from "next/link";
import { claims } from "@/lib/claims";

export const metadata: Metadata = {
  title: "California Employment Law Claim Types — Find Legal Help",
  description:
    "Browse California employment claim types — wrongful termination, discrimination, harassment, wage theft, retaliation, PAGA, CFRA leave, and misclassification. AI-powered guidance.",
};

export default function ClaimsIndex() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <span className="text-text-primary">Claims</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          California Employment Claim Types
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Learn about common employment law claims in California, or{" "}
          <Link
            href="/"
            className="text-accent underline hover:text-accent-hover"
          >
            ask a specific question
          </Link>
          .
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {claims.map((claim) => (
            <Link
              key={claim.slug}
              href={`/claims/${claim.slug}`}
              className="rounded-lg border border-border p-5 transition-colors hover:border-border-hover hover:bg-accent-surface"
            >
              <h2 className="font-semibold text-text-primary">
                {claim.shortTitle}
              </h2>
              <p className="mt-2 text-sm text-text-tertiary">
                {claim.description}
              </p>
              <div className="mt-3 flex flex-wrap gap-1">
                {claim.primaryAgencies.map((a) => (
                  <span
                    key={a}
                    className="rounded-full bg-accent-surface px-2 py-0.5 text-xs text-accent"
                  >
                    {a}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
