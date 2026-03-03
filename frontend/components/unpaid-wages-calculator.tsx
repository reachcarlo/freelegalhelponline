"use client";

import { useState } from "react";
import Link from "next/link";
import {
  calculateUnpaidWages,
  type WageBreakdownInfo,
  type UnpaidWagesResponse,
} from "@/lib/calculators/unpaid-wages";

const EMPLOYMENT_STATUSES = [
  { value: "still_employed", label: "Still Employed" },
  { value: "terminated", label: "Terminated / Fired" },
  { value: "quit_with_notice", label: "Quit (72+ hours notice)" },
  { value: "quit_without_notice", label: "Quit (no notice)" },
] as const;

function categoryColor(category: string): string {
  switch (category) {
    case "waiting_time_penalty":
      return "border-l-4 border-l-warning-border bg-warning-bg";
    case "interest":
      return "border-l-4 border-l-border bg-surface-raised";
    case "meal_break_premium":
    case "rest_break_premium":
      return "border-l-4 border-l-accent bg-accent-surface";
    default:
      return "border-l-4 border-l-accent bg-surface-raised";
  }
}

export default function UnpaidWagesCalculator() {
  const [hourlyRate, setHourlyRate] = useState("");
  const [unpaidHours, setUnpaidHours] = useState("");
  const [employmentStatus, setEmploymentStatus] = useState("still_employed");
  const [terminationDate, setTerminationDate] = useState("");
  const [finalWagesPaidDate, setFinalWagesPaidDate] = useState("");
  const [missedMealBreaks, setMissedMealBreaks] = useState("0");
  const [missedRestBreaks, setMissedRestBreaks] = useState("0");
  const [unpaidSince, setUnpaidSince] = useState("");
  const [result, setResult] = useState<UnpaidWagesResponse | null>(null);
  const [error, setError] = useState("");

  const showTerminationFields = employmentStatus !== "still_employed";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!hourlyRate || !unpaidHours) return;

    setError("");
    setResult(null);

    try {
      const data = calculateUnpaidWages(
        parseFloat(hourlyRate),
        parseFloat(unpaidHours),
        employmentStatus,
        showTerminationFields && terminationDate ? terminationDate : undefined,
        showTerminationFields && finalWagesPaidDate
          ? finalWagesPaidDate
          : undefined,
        parseInt(missedMealBreaks) || 0,
        parseInt(missedRestBreaks) || 0,
        unpaidSince || undefined
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  function formatCurrency(amount: string): string {
    const num = parseFloat(amount);
    return num.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Hourly rate */}
        <div>
          <label
            htmlFor="hourly-rate"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Hourly Rate ($)
          </label>
          <input
            id="hourly-rate"
            type="number"
            step="0.01"
            min="0.01"
            max="1000"
            value={hourlyRate}
            onChange={(e) => setHourlyRate(e.target.value)}
            placeholder="e.g. 20.00"
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            required
          />
        </div>

        {/* Unpaid hours */}
        <div>
          <label
            htmlFor="unpaid-hours"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Unpaid Hours
          </label>
          <input
            id="unpaid-hours"
            type="number"
            step="0.5"
            min="0"
            max="10000"
            value={unpaidHours}
            onChange={(e) => setUnpaidHours(e.target.value)}
            placeholder="e.g. 40"
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            required
          />
        </div>

        {/* Employment status */}
        <div>
          <label
            htmlFor="employment-status"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Employment Status
          </label>
          <select
            id="employment-status"
            value={employmentStatus}
            onChange={(e) => setEmploymentStatus(e.target.value)}
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {EMPLOYMENT_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Conditional termination fields */}
        {showTerminationFields && (
          <>
            <div>
              <label
                htmlFor="termination-date"
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                Termination / Last Day of Work
              </label>
              <input
                id="termination-date"
                type="date"
                value={terminationDate}
                onChange={(e) => setTerminationDate(e.target.value)}
                className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                required
              />
            </div>

            <div>
              <label
                htmlFor="final-wages-paid-date"
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                Date Final Wages Were Paid{" "}
                <span className="text-text-tertiary font-normal">
                  (leave blank if still unpaid)
                </span>
              </label>
              <input
                id="final-wages-paid-date"
                type="date"
                value={finalWagesPaidDate}
                onChange={(e) => setFinalWagesPaidDate(e.target.value)}
                className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
          </>
        )}

        {/* Missed breaks */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="missed-meal-breaks"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Missed Meal Breaks
            </label>
            <input
              id="missed-meal-breaks"
              type="number"
              min="0"
              max="1000"
              value={missedMealBreaks}
              onChange={(e) => setMissedMealBreaks(e.target.value)}
              className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <div>
            <label
              htmlFor="missed-rest-breaks"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Missed Rest Breaks
            </label>
            <input
              id="missed-rest-breaks"
              type="number"
              min="0"
              max="1000"
              value={missedRestBreaks}
              onChange={(e) => setMissedRestBreaks(e.target.value)}
              className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        </div>

        {/* Unpaid since (for interest) */}
        <div>
          <label
            htmlFor="unpaid-since"
            className="block text-sm font-medium text-text-secondary mb-1"
          >
            Wages Owed Since{" "}
            <span className="text-text-tertiary font-normal">
              (optional, for interest calculation)
            </span>
          </label>
          <input
            id="unpaid-since"
            type="date"
            value={unpaidSince}
            onChange={(e) => setUnpaidSince(e.target.value)}
            className="w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <button
          type="submit"
          disabled={!hourlyRate || !unpaidHours}
          className="min-h-[44px] w-full rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Calculate Damages
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          {/* Total */}
          <div className="rounded-lg border border-accent bg-accent-surface p-5 text-center">
            <p className="text-sm font-medium text-text-secondary">
              Estimated Total
            </p>
            <p className="mt-1 text-3xl font-bold text-text-primary">
              ${formatCurrency(result.total)}
            </p>
          </div>

          {/* Breakdown */}
          <div className="space-y-3">
            {result.items.map((item, i) => (
              <div
                key={i}
                className={`rounded-lg border border-border p-4 ${categoryColor(item.category)}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-text-primary">
                      {item.label}
                    </h3>
                    <p className="mt-1 text-sm text-text-secondary">
                      {item.description}
                    </p>
                  </div>
                  <p className="text-lg font-bold text-text-primary whitespace-nowrap">
                    ${formatCurrency(item.amount)}
                  </p>
                </div>
                <div className="mt-2 flex items-center flex-wrap gap-x-4 gap-y-1">
                  <span className="text-xs text-text-tertiary">
                    {item.legal_citation}
                  </span>
                  {item.notes && (
                    <span className="text-xs text-text-tertiary italic">
                      {item.notes}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Cross-links */}
          <div className="flex flex-wrap gap-4 text-sm">
            <Link
              href="/tools/deadline-calculator"
              className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
            >
              Check your deadlines &rarr;
            </Link>
            <Link
              href="/tools/agency-routing"
              className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
            >
              Find where to file &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
