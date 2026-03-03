/**
 * Client-side unpaid wages calculator.
 *
 * Ports the Python backend calculator to TypeScript so the component can
 * compute results locally without a network round-trip.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface WageBreakdownInfo {
  category: string;
  label: string;
  amount: string;
  legal_citation: string;
  description: string;
  notes: string;
}

export interface UnpaidWagesResponse {
  items: WageBreakdownInfo[];
  total: string;
  hourly_rate: string;
  unpaid_hours: string;
  disclaimer: string;
}

// ── Helpers ──────────────────────────────────────────────────────────

const DISCLAIMER =
  "This calculator provides general estimates based on California labor law. " +
  "Actual amounts may vary depending on your specific employment agreement, " +
  "applicable exemptions, collective bargaining agreements, overtime rates, " +
  "and other factors. Waiting time penalties and interest calculations are " +
  "simplified estimates. Consult a licensed California employment attorney " +
  "for advice about your specific situation.";

/** Format a number to exactly 2 decimal places. */
function fmt(n: number): string {
  return n.toFixed(2);
}

/**
 * Return the number of whole calendar days between two ISO date strings
 * (or Date objects). The result is always >= 0.
 */
function daysBetween(startIso: string | Date, endIso: string | Date): number {
  const start = typeof startIso === "string" ? new Date(startIso) : startIso;
  const end = typeof endIso === "string" ? new Date(endIso) : endIso;
  const msPerDay = 86_400_000;
  // Strip time components by using UTC dates to avoid DST issues.
  const startUtc = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const endUtc = Date.UTC(end.getFullYear(), end.getMonth(), end.getDate());
  const diff = Math.floor((endUtc - startUtc) / msPerDay);
  return Math.max(0, diff);
}

/** Add `days` calendar days to an ISO date string and return a new Date. */
function addDays(isoDate: string, days: number): Date {
  const d = new Date(isoDate);
  d.setDate(d.getDate() + days);
  return d;
}

/** Today as an ISO date string (YYYY-MM-DD). */
function todayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// ── Main calculator ──────────────────────────────────────────────────

export function calculateUnpaidWages(
  hourlyRate: number,
  unpaidHours: number,
  employmentStatus: string,
  terminationDate?: string,
  finalWagesPaidDate?: string,
  missedMealBreaks?: number,
  missedRestBreaks?: number,
  unpaidSince?: string,
): UnpaidWagesResponse {
  const items: WageBreakdownInfo[] = [];

  // 1. Unpaid Wages ──────────────────────────────────────────────────
  const unpaidWages = hourlyRate * unpaidHours;
  items.push({
    category: "unpaid_wages",
    label: "Unpaid Wages",
    amount: fmt(unpaidWages),
    legal_citation: "Lab. Code \u00a7\u00a7200\u2013204",
    description: `${unpaidHours} hours \u00d7 $${fmt(hourlyRate)}/hr`,
    notes: "",
  });

  // 2. Meal Break Premiums ───────────────────────────────────────────
  const mealBreaks = missedMealBreaks ?? 0;
  if (mealBreaks > 0) {
    const mealPremium = hourlyRate * mealBreaks;
    items.push({
      category: "meal_break_premium",
      label: "Meal Break Premiums",
      amount: fmt(mealPremium),
      legal_citation: "Lab. Code \u00a7226.7(c)",
      description: `${mealBreaks} missed break(s) \u00d7 $${fmt(hourlyRate)}/hr (1 hour premium per violation)`,
      notes: "",
    });
  }

  // 3. Rest Break Premiums ───────────────────────────────────────────
  const restBreaks = missedRestBreaks ?? 0;
  if (restBreaks > 0) {
    const restPremium = hourlyRate * restBreaks;
    items.push({
      category: "rest_break_premium",
      label: "Rest Break Premiums",
      amount: fmt(restPremium),
      legal_citation: "Lab. Code \u00a7226.7(c)",
      description: `${restBreaks} missed break(s) \u00d7 $${fmt(hourlyRate)}/hr (1 hour premium per violation)`,
      notes: "",
    });
  }

  // 4. Waiting Time Penalty ──────────────────────────────────────────
  const isStillEmployed = employmentStatus === "still_employed";
  if (!isStillEmployed && terminationDate) {
    const dailyWage = hourlyRate * 8;

    // Payment due date depends on how the employee left.
    let paymentDueDate: Date;
    if (employmentStatus === "quit_without_notice") {
      paymentDueDate = addDays(terminationDate, 3);
    } else {
      // terminated or quit_with_notice: wages due on termination date
      paymentDueDate = new Date(terminationDate);
    }

    const paidDateIso = finalWagesPaidDate || todayIso();
    const paidDate = new Date(paidDateIso);

    if (paidDate > paymentDueDate) {
      const daysLate = Math.min(
        daysBetween(paymentDueDate, paidDate),
        30,
      );
      const penalty = dailyWage * daysLate;
      items.push({
        category: "waiting_time_penalty",
        label: "Waiting Time Penalty",
        amount: fmt(penalty),
        legal_citation: "Lab. Code \u00a7203",
        description: `$${fmt(dailyWage)}/day \u00d7 ${daysLate} day(s) late (max 30 days)`,
        notes: "",
      });
    } else {
      items.push({
        category: "waiting_time_penalty",
        label: "Waiting Time Penalty",
        amount: "0.00",
        legal_citation: "Lab. Code \u00a7203",
        description: "No penalty \u2014 final wages paid on time",
        notes: "",
      });
    }
  }

  // 5. Prejudgment Interest ──────────────────────────────────────────
  if (unpaidSince && unpaidWages > 0) {
    const days = daysBetween(unpaidSince, todayIso());
    const interest = unpaidWages * 0.10 * days / 365;
    items.push({
      category: "interest",
      label: "Prejudgment Interest",
      amount: fmt(interest),
      legal_citation: "Civ. Code \u00a73287(a); Cal. Const. Art. XV \u00a71",
      description: `10% annual on $${fmt(unpaidWages)} over ${days} day(s)`,
      notes: "",
    });
  }

  // ── Totals ────────────────────────────────────────────────────────
  const total = items.reduce((sum, item) => sum + parseFloat(item.amount), 0);

  return {
    items,
    total: fmt(total),
    hourly_rate: fmt(hourlyRate),
    unpaid_hours: fmt(unpaidHours),
    disclaimer: DISCLAIMER,
  };
}
