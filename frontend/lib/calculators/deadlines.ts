/**
 * Client-side deadline calculator for California employment claims.
 * Ports the Python deadline calculator to TypeScript so results
 * can be computed without a backend round-trip.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface DeadlineInfo {
  name: string;
  description: string;
  filing_entity: string;
  legal_citation: string;
  portal_url: string;
  notes: string;
  deadline_date: string;
  days_remaining: number;
  urgency: "expired" | "critical" | "urgent" | "normal";
}

export interface DeadlineResponse {
  claim_type: string;
  claim_type_label: string;
  incident_date: string;
  deadlines: DeadlineInfo[];
  disclaimer: string;
}

// ── Claim type labels ────────────────────────────────────────────────

const CLAIM_TYPE_LABELS: Record<string, string> = {
  feha_discrimination: "FEHA Discrimination / Harassment",
  wage_theft: "Wage Theft / Unpaid Wages",
  wrongful_termination: "Wrongful Termination",
  retaliation_whistleblower: "Retaliation / Whistleblower",
  paga: "PAGA (Private Attorneys General Act)",
  cfra_family_leave: "CFRA / Family Leave Violations",
  government_employee: "Government Employee Claims",
  misclassification: "Worker Misclassification",
};

// ── Deadline rule definitions ────────────────────────────────────────

interface DeadlineRule {
  name: string;
  description: string;
  filing_entity: string;
  legal_citation: string;
  portal_url: string;
  notes?: string;
  years?: number;
  months?: number;
  days?: number;
}

const DEADLINE_RULES: Record<string, DeadlineRule[]> = {
  feha_discrimination: [
    {
      name: "CRD Complaint",
      description:
        "File a complaint with the California Civil Rights Department (formerly DFEH).",
      filing_entity: "Civil Rights Department (CRD)",
      legal_citation: "Gov. Code \u00a712960(d)",
      portal_url: "https://calcivilrights.ca.gov/complaintprocess/",
      years: 3,
    },
    {
      name: "EEOC Charge",
      description:
        "File a charge with the Equal Employment Opportunity Commission (federal cross-file).",
      filing_entity: "EEOC",
      legal_citation: "42 U.S.C. \u00a72000e-5(e)",
      portal_url: "https://www.eeoc.gov/filing-charge-discrimination",
      notes:
        "300-day deadline applies because California has a state agency (CRD) with a work-sharing agreement.",
      days: 300,
    },
    {
      name: "Civil Suit (Right-to-Sue)",
      description:
        "File a civil lawsuit after obtaining a right-to-sue notice from CRD.",
      filing_entity: "Superior Court",
      legal_citation: "Gov. Code \u00a712965(b)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      notes:
        "Must first file with CRD and obtain right-to-sue letter. Statute runs from the discriminatory act, not the letter.",
      years: 4,
    },
  ],

  wage_theft: [
    {
      name: "DLSE / Labor Commissioner Claim",
      description:
        "File a wage claim with the Division of Labor Standards Enforcement.",
      filing_entity: "Labor Commissioner (DLSE)",
      legal_citation: "Lab. Code \u00a798; CCP \u00a7338(a)",
      portal_url:
        "https://www.dir.ca.gov/dlse/howtofilewageclaim.htm",
      years: 3,
    },
    {
      name: "Court Action \u2014 Oral Agreement",
      description:
        "Sue for unpaid wages based on an oral employment agreement.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7339(1)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-smallclaims.htm",
      notes:
        "Applies to verbal promises of pay, bonuses, or commissions.",
      years: 2,
    },
    {
      name: "Court Action \u2014 Written Agreement",
      description:
        "Sue for unpaid wages based on a written employment agreement.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7337(a)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-smallclaims.htm",
      years: 4,
    },
    {
      name: "UCL (Unfair Business Practices)",
      description:
        "Sue under California's Unfair Competition Law for unlawful wage practices.",
      filing_entity: "Superior Court",
      legal_citation: "Bus. & Prof. Code \u00a717208",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      notes:
        "Allows recovery of wages as restitution; no punitive damages.",
      years: 4,
    },
    {
      name: "PAGA Notice (Wage Violations)",
      description:
        "Send notice to LWDA before filing a PAGA action for wage violations.",
      filing_entity: "LWDA",
      legal_citation: "Lab. Code \u00a72699.3(a)",
      portal_url:
        "https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
      notes:
        "Must send LWDA notice before filing suit. Court action within 65 days after notice.",
      years: 1,
    },
  ],

  wrongful_termination: [
    {
      name: "Tort Claim (Public Policy)",
      description:
        "File a wrongful termination in violation of public policy lawsuit.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7335.1",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      years: 2,
    },
    {
      name: "Breach of Oral Contract",
      description:
        "Sue for wrongful termination based on an oral employment agreement.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7339(1)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      years: 2,
    },
    {
      name: "Breach of Written Contract",
      description:
        "Sue for wrongful termination based on a written employment agreement.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7337(a)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      years: 4,
    },
  ],

  retaliation_whistleblower: [
    {
      name: "Court Action (Lab. Code \u00a71102.5)",
      description:
        "File a whistleblower retaliation lawsuit in court.",
      filing_entity: "Superior Court",
      legal_citation: "Lab. Code \u00a71102.5; CCP \u00a7338",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      years: 3,
    },
    {
      name: "DLSE Retaliation Complaint",
      description:
        "File a retaliation complaint with the Labor Commissioner.",
      filing_entity: "Labor Commissioner (DLSE)",
      legal_citation: "Lab. Code \u00a798.6",
      portal_url:
        "https://www.dir.ca.gov/dlse/howtofileretaliation.htm",
      notes:
        "Shorter deadline than court action. DLSE investigates and may hold a hearing.",
      months: 6,
    },
  ],

  paga: [
    {
      name: "LWDA Notice",
      description:
        "Send written notice to the Labor and Workforce Development Agency and employer.",
      filing_entity: "LWDA",
      legal_citation: "Lab. Code \u00a72699.3(a)(2)",
      portal_url:
        "https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
      notes:
        "Required before filing suit. LWDA has 65 days to respond.",
      years: 1,
    },
    {
      name: "Court Filing After LWDA Notice",
      description:
        "File PAGA action in court after the 65-day LWDA notice period.",
      filing_entity: "Superior Court",
      legal_citation: "Lab. Code \u00a72699.3(a)(2)(A)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      notes:
        "65 calendar days after LWDA notice, if LWDA does not investigate. Starts from incident date + 65 days for calculation purposes.",
      days: 430,
    },
  ],

  cfra_family_leave: [
    {
      name: "CRD Complaint",
      description:
        "File a CFRA violation complaint with the Civil Rights Department.",
      filing_entity: "Civil Rights Department (CRD)",
      legal_citation: "Gov. Code \u00a712945.2; Gov. Code \u00a712960",
      portal_url: "https://calcivilrights.ca.gov/complaintprocess/",
      years: 3,
    },
    {
      name: "EEOC Charge (FMLA Cross-File)",
      description:
        "File a charge with the EEOC for related federal FMLA violations.",
      filing_entity: "EEOC",
      legal_citation: "29 U.S.C. \u00a72617",
      portal_url: "https://www.eeoc.gov/filing-charge-discrimination",
      notes:
        "For federal FMLA claims. California CFRA claims go through CRD.",
      days: 300,
    },
  ],

  government_employee: [
    {
      name: "Government Tort Claim",
      description:
        "File a tort claim with the employing government agency before suing.",
      filing_entity: "Government Agency",
      legal_citation: "Gov. Code \u00a7911.2",
      portal_url:
        "https://www.courts.ca.gov/documents/govt-tort-claim.pdf",
      notes:
        "Must file tort claim BEFORE filing a lawsuit. Deadline runs from the date of the incident.",
      months: 6,
    },
    {
      name: "Court Action After Claim Denial",
      description:
        "File a lawsuit after the government denies your tort claim (or fails to respond in 45 days).",
      filing_entity: "Superior Court",
      legal_citation: "Gov. Code \u00a7945.6",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      notes:
        "6 months to file tort claim + 6 months after denial. This is the outer limit from the incident date.",
      months: 12,
    },
  ],

  misclassification: [
    {
      name: "DLSE Misclassification Complaint",
      description:
        "File a misclassification complaint with the Labor Commissioner.",
      filing_entity: "Labor Commissioner (DLSE)",
      legal_citation: "Lab. Code \u00a7226.8",
      portal_url:
        "https://www.dir.ca.gov/dlse/howtofilewageclaim.htm",
      years: 3,
    },
    {
      name: "Court Action \u2014 Unpaid Wages",
      description:
        "Sue for unpaid wages and benefits resulting from misclassification.",
      filing_entity: "Superior Court",
      legal_citation: "CCP \u00a7338(a)",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-smallclaims.htm",
      years: 3,
    },
    {
      name: "UCL (Unfair Business Practices)",
      description:
        "Sue under the UCL for misclassification as an unfair business practice.",
      filing_entity: "Superior Court",
      legal_citation: "Bus. & Prof. Code \u00a717208",
      portal_url:
        "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
      notes: "Allows recovery of wages as restitution.",
      years: 4,
    },
  ],
};

// ── Disclaimer ───────────────────────────────────────────────────────

const DISCLAIMER =
  "These deadlines are general estimates based on California law. " +
  "Actual deadlines may vary depending on tolling, discovery rules, " +
  "continuing violations, or other legal doctrines. Weekend/holiday " +
  "adjustments are not applied (CCP \u00a712a applies only to specific " +
  "court filing deadlines). Consult a licensed California employment " +
  "attorney for advice about your specific situation.";

// ── Date arithmetic helpers ──────────────────────────────────────────

/**
 * Return true if `year` is a leap year.
 */
function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

/**
 * Return the number of days in a given month (1-indexed).
 */
function daysInMonth(year: number, month: number): number {
  // month is 1-indexed
  const table = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month === 2 && isLeapYear(year)) return 29;
  return table[month];
}

/**
 * Parse an ISO date string (YYYY-MM-DD) into { year, month, day }.
 */
function parseDate(iso: string): { year: number; month: number; day: number } {
  const parts = iso.split("-");
  return {
    year: parseInt(parts[0], 10),
    month: parseInt(parts[1], 10),
    day: parseInt(parts[2], 10),
  };
}

/**
 * Format { year, month, day } as an ISO date string (YYYY-MM-DD).
 */
function formatDate(year: number, month: number, day: number): string {
  const yStr = String(year).padStart(4, "0");
  const mStr = String(month).padStart(2, "0");
  const dStr = String(day).padStart(2, "0");
  return `${yStr}-${mStr}-${dStr}`;
}

/**
 * Add `n` years to a date, clamping Feb 29 to Feb 28 in non-leap years.
 */
function addYears(iso: string, n: number): string {
  const d = parseDate(iso);
  const newYear = d.year + n;
  const maxDay = daysInMonth(newYear, d.month);
  const newDay = Math.min(d.day, maxDay);
  return formatDate(newYear, d.month, newDay);
}

/**
 * Add `n` months to a date, clamping the day to month-end when needed.
 */
function addMonths(iso: string, n: number): string {
  const d = parseDate(iso);
  // Total months from year 0, then divide back
  const totalMonths = d.year * 12 + (d.month - 1) + n;
  const newYear = Math.floor(totalMonths / 12);
  const newMonth = (totalMonths % 12) + 1;
  const maxDay = daysInMonth(newYear, newMonth);
  const newDay = Math.min(d.day, maxDay);
  return formatDate(newYear, newMonth, newDay);
}

/**
 * Add `n` days to a date via a JavaScript Date object.
 */
function addDays(iso: string, n: number): string {
  const d = parseDate(iso);
  // Use UTC to avoid DST issues
  const date = new Date(Date.UTC(d.year, d.month - 1, d.day));
  date.setUTCDate(date.getUTCDate() + n);
  return formatDate(
    date.getUTCFullYear(),
    date.getUTCMonth() + 1,
    date.getUTCDate()
  );
}

/**
 * Compute the deadline date from an incident date and a rule.
 */
function computeDeadlineDate(incidentDate: string, rule: DeadlineRule): string {
  if (rule.years !== undefined) {
    return addYears(incidentDate, rule.years);
  }
  if (rule.months !== undefined) {
    return addMonths(incidentDate, rule.months);
  }
  if (rule.days !== undefined) {
    return addDays(incidentDate, rule.days);
  }
  // Fallback — should never happen with valid rules
  return incidentDate;
}

/**
 * Compute the number of calendar days between two ISO date strings.
 * Positive when `deadline` is in the future relative to `today`.
 */
function daysBetween(today: string, deadline: string): number {
  const t = parseDate(today);
  const d = parseDate(deadline);
  const todayMs = Date.UTC(t.year, t.month - 1, t.day);
  const deadlineMs = Date.UTC(d.year, d.month - 1, d.day);
  return Math.round((deadlineMs - todayMs) / (1000 * 60 * 60 * 24));
}

/**
 * Determine urgency from days remaining.
 */
function urgencyFromDays(
  daysRemaining: number
): "expired" | "critical" | "urgent" | "normal" {
  if (daysRemaining < 0) return "expired";
  if (daysRemaining < 30) return "critical";
  if (daysRemaining < 90) return "urgent";
  return "normal";
}

// ── Main calculation function ────────────────────────────────────────

/**
 * Calculate statute-of-limitations deadlines for a California employment
 * claim entirely on the client side (no network call required).
 *
 * @param claimType  One of the keys in CLAIM_TYPE_LABELS.
 * @param incidentDate  ISO date string (YYYY-MM-DD) of the incident.
 * @returns A DeadlineResponse with computed deadlines sorted by date ascending.
 */
export function calculateDeadlines(
  claimType: string,
  incidentDate: string
): DeadlineResponse {
  const label = CLAIM_TYPE_LABELS[claimType];
  if (!label) {
    throw new Error(`Unknown claim type: ${claimType}`);
  }

  const rules = DEADLINE_RULES[claimType];
  if (!rules) {
    throw new Error(`No deadline rules for claim type: ${claimType}`);
  }

  // Today in ISO format (local time zone, date only)
  const now = new Date();
  const todayIso = formatDate(
    now.getFullYear(),
    now.getMonth() + 1,
    now.getDate()
  );

  const deadlines: DeadlineInfo[] = rules.map((rule) => {
    const deadlineDate = computeDeadlineDate(incidentDate, rule);
    const daysRemaining = daysBetween(todayIso, deadlineDate);
    return {
      name: rule.name,
      description: rule.description,
      filing_entity: rule.filing_entity,
      legal_citation: rule.legal_citation,
      portal_url: rule.portal_url,
      notes: rule.notes ?? "",
      deadline_date: deadlineDate,
      days_remaining: daysRemaining,
      urgency: urgencyFromDays(daysRemaining),
    };
  });

  // Sort by deadline_date ascending
  deadlines.sort((a, b) => (a.deadline_date < b.deadline_date ? -1 : 1));

  return {
    claim_type: claimType,
    claim_type_label: label,
    incident_date: incidentDate,
    deadlines,
    disclaimer: DISCLAIMER,
  };
}
