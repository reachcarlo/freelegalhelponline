"use client";

import { useState } from "react";
import Link from "next/link";
import {
  getAgencyRouting,
  type AgencyRecommendationInfo,
  type AgencyRoutingResponse,
} from "@/lib/api";

const ISSUE_TYPES = [
  { value: "unpaid_wages", label: "Unpaid Wages / Wage Theft" },
  {
    value: "discrimination",
    label: "Discrimination (Race, Gender, Age, Disability, etc.)",
  },
  { value: "harassment", label: "Harassment / Hostile Work Environment" },
  { value: "wrongful_termination", label: "Wrongful Termination" },
  { value: "retaliation", label: "Retaliation for Exercising Rights" },
  { value: "family_medical_leave", label: "Family / Medical Leave Violations" },
  { value: "workplace_safety", label: "Workplace Safety / Health Hazards" },
  {
    value: "misclassification",
    label: "Worker Misclassification (1099 vs W-2)",
  },
  { value: "unemployment_benefits", label: "Unemployment Insurance Benefits" },
  { value: "disability_insurance", label: "State Disability Insurance (SDI)" },
  { value: "paid_family_leave", label: "Paid Family Leave (PFL)" },
  { value: "meal_rest_breaks", label: "Meal / Rest Break Violations" },
  { value: "whistleblower", label: "Whistleblower Protections" },
] as const;

function priorityBadge(priority: AgencyRecommendationInfo["priority"]) {
  switch (priority) {
    case "prerequisite":
      return (
        <span className="inline-flex items-center rounded-full bg-warning-bg border border-warning-border px-2.5 py-0.5 text-xs font-medium text-warning-text">
          Prerequisite
        </span>
      );
    case "primary":
      return (
        <span className="inline-flex items-center rounded-full bg-accent-surface border border-accent px-2.5 py-0.5 text-xs font-medium text-accent">
          Primary
        </span>
      );
    case "alternative":
      return (
        <span className="inline-flex items-center rounded-full bg-badge-bg border border-border px-2.5 py-0.5 text-xs font-medium text-text-secondary">
          Alternative
        </span>
      );
  }
}

function cardClasses(priority: AgencyRecommendationInfo["priority"]): string {
  switch (priority) {
    case "primary":
      return "border-border bg-surface-raised border-l-4 border-l-accent";
    case "prerequisite":
      return "border-warning-border bg-warning-bg";
    default:
      return "border-border bg-surface-raised";
  }
}

export default function AgencyRouting() {
  const [issueType, setIssueType] = useState("");
  const [isGovEmployee, setIsGovEmployee] = useState(false);
  const [result, setResult] = useState<AgencyRoutingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!issueType) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const data = await getAgencyRouting(issueType, isGovEmployee);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="issue-type"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            What is your employment issue?
          </label>
          <select
            id="issue-type"
            value={issueType}
            onChange={(e) => setIssueType(e.target.value)}
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            required
          >
            <option value="">Select an issue type...</option>
            {ISSUE_TYPES.map((it) => (
              <option key={it.value} value={it.value}>
                {it.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="gov-employee"
            type="checkbox"
            checked={isGovEmployee}
            onChange={(e) => setIsGovEmployee(e.target.checked)}
            className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
          />
          <label
            htmlFor="gov-employee"
            className="text-sm text-text-secondary"
          >
            I am a government employee
          </label>
        </div>

        <button
          type="submit"
          disabled={loading || !issueType}
          className="min-h-[44px] w-full rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Finding agencies..." : "Find the Right Agency"}
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
            {result.issue_type_label}
          </h2>
          {result.is_government_employee && (
            <p className="text-sm text-text-secondary">
              Showing results for government employees
            </p>
          )}

          <div className="space-y-3">
            {result.recommendations.map((rec, i) => (
              <div
                key={i}
                className={`rounded-lg border p-4 ${cardClasses(rec.priority)}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-text-primary">
                        {rec.agency_name} ({rec.agency_acronym})
                      </h3>
                      {priorityBadge(rec.priority)}
                    </div>
                    <p className="mt-1 text-sm text-text-secondary">
                      {rec.reason}
                    </p>
                  </div>
                </div>

                <div className="mt-3 space-y-2">
                  <div>
                    <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
                      What to file
                    </p>
                    <p className="text-sm text-text-primary">
                      {rec.what_to_file}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
                      Filing methods
                    </p>
                    <p className="text-sm text-text-primary">
                      {rec.filing_methods.join(" · ")}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
                      Process overview
                    </p>
                    <p className="text-sm text-text-secondary">
                      {rec.process_overview}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
                      Typical timeline
                    </p>
                    <p className="text-sm text-text-secondary">
                      {rec.typical_timeline}
                    </p>
                  </div>
                </div>

                {rec.notes && (
                  <p className="mt-2 text-xs text-text-tertiary italic">
                    {rec.notes}
                  </p>
                )}

                <div className="mt-3 flex items-center flex-wrap gap-x-4 gap-y-2 text-sm">
                  {rec.portal_url && (
                    <a
                      href={rec.portal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover underline"
                    >
                      Visit portal
                    </a>
                  )}
                  {rec.phone && (
                    <a
                      href={`tel:${rec.phone.replace(/[^+\d]/g, "")}`}
                      className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover underline"
                    >
                      {rec.phone}
                    </a>
                  )}
                  {rec.related_claim_type && (
                    <Link
                      href="/tools/deadline-calculator"
                      className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
                    >
                      Check your deadlines &rarr;
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
