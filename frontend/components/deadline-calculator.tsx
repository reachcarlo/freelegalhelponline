"use client";

import { useState } from "react";
import Link from "next/link";
import {
  calculateDeadlines,
  type DeadlineInfo,
  type DeadlineResponse,
} from "@/lib/calculators/deadlines";

const CLAIM_TYPES = [
  { value: "feha_discrimination", label: "FEHA Discrimination / Harassment" },
  { value: "wage_theft", label: "Wage Theft / Unpaid Wages" },
  { value: "wrongful_termination", label: "Wrongful Termination" },
  {
    value: "retaliation_whistleblower",
    label: "Retaliation / Whistleblower",
  },
  { value: "paga", label: "PAGA (Private Attorneys General Act)" },
  { value: "cfra_family_leave", label: "CFRA / Family Leave Violations" },
  { value: "government_employee", label: "Government Employee Claims" },
  { value: "misclassification", label: "Worker Misclassification" },
] as const;

function urgencyBadge(urgency: DeadlineInfo["urgency"]) {
  switch (urgency) {
    case "expired":
      return (
        <span className="inline-flex items-center rounded-full bg-error-bg border border-error-border px-2.5 py-0.5 text-xs font-medium text-error-text">
          Expired
        </span>
      );
    case "critical":
      return (
        <span className="inline-flex items-center rounded-full bg-error-bg border border-error-border px-2.5 py-0.5 text-xs font-medium text-error-text">
          Critical
        </span>
      );
    case "urgent":
      return (
        <span className="inline-flex items-center rounded-full bg-warning-bg border border-warning-border px-2.5 py-0.5 text-xs font-medium text-warning-text">
          Urgent
        </span>
      );
    default:
      return null;
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function daysLabel(days: number): string {
  if (days < 0) return `${Math.abs(days)} days ago`;
  if (days === 0) return "Today";
  if (days === 1) return "1 day remaining";
  return `${days} days remaining`;
}

function cardClasses(urgency: DeadlineInfo["urgency"]): string {
  switch (urgency) {
    case "expired":
    case "critical":
      return "border-error-border bg-error-bg";
    case "urgent":
      return "border-warning-border bg-warning-bg";
    default:
      return "border-border bg-surface-raised";
  }
}

export default function DeadlineCalculator() {
  const [claimType, setClaimType] = useState("");
  const [incidentDate, setIncidentDate] = useState("");
  const [result, setResult] = useState<DeadlineResponse | null>(null);
  const [error, setError] = useState("");

  const today = new Date().toISOString().split("T")[0];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!claimType || !incidentDate) return;

    setError("");
    setResult(null);

    try {
      const data = calculateDeadlines(claimType, incidentDate);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="claim-type"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Claim Type
          </label>
          <select
            id="claim-type"
            value={claimType}
            onChange={(e) => setClaimType(e.target.value)}
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            required
          >
            <option value="">Select a claim type...</option>
            {CLAIM_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>
                {ct.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="incident-date"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Date of Incident
          </label>
          <input
            id="incident-date"
            type="date"
            value={incidentDate}
            max={today}
            onChange={(e) => setIncidentDate(e.target.value)}
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            required
          />
        </div>

        <button
          type="submit"
          disabled={!claimType || !incidentDate}
          className="min-h-[44px] w-full rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Calculate Deadlines
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">
            {result.claim_type_label}
          </h2>
          <p className="text-sm text-text-secondary">
            Incident date: {formatDate(result.incident_date)}
          </p>

          <div className="space-y-3">
            {result.deadlines.map((dl, i) => (
              <div
                key={i}
                className={`rounded-lg border p-4 ${cardClasses(dl.urgency)}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-text-primary">
                        {dl.name}
                      </h3>
                      {urgencyBadge(dl.urgency)}
                    </div>
                    <p className="mt-1 text-sm text-text-secondary">
                      {dl.filing_entity}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-medium text-text-primary">
                      {formatDate(dl.deadline_date)}
                    </p>
                    <p
                      className={`text-sm ${
                        dl.urgency === "expired" || dl.urgency === "critical"
                          ? "text-error-text font-medium"
                          : dl.urgency === "urgent"
                            ? "text-warning-text font-medium"
                            : "text-text-secondary"
                      }`}
                    >
                      {daysLabel(dl.days_remaining)}
                    </p>
                  </div>
                </div>

                <p className="mt-2 text-sm text-text-secondary">
                  {dl.description}
                </p>

                {dl.notes && (
                  <p className="mt-1 text-xs text-text-tertiary italic">
                    {dl.notes}
                  </p>
                )}

                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-text-tertiary">
                    {dl.legal_citation}
                  </span>
                  {dl.portal_url && (
                    <a
                      href={dl.portal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:text-accent-hover underline"
                    >
                      Filing portal
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Cross-links */}
          <div className="flex flex-wrap gap-4 text-sm">
            <Link
              href="/tools/agency-routing"
              className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
            >
              Find where to file &rarr;
            </Link>
            <Link
              href="/tools/incident-docs"
              className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
            >
              Document what happened &rarr;
            </Link>
            <Link
              href="/tools/unpaid-wages-calculator"
              className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
            >
              Calculate unpaid wages &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
