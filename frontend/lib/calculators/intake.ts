/**
 * Client-side guided intake questionnaire for California employment issues.
 * Ports the Python intake engine to TypeScript so results
 * can be computed without a backend round-trip.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface AnswerOption {
  key: string;
  label: string;
  help_text: string;
}

export interface IntakeQuestion {
  question_id: string;
  question_text: string;
  help_text: string;
  options: AnswerOption[];
  allow_multiple: boolean;
  show_if: string[] | null;
}

export interface ToolRecommendation {
  tool_name: string;
  tool_label: string;
  tool_path: string;
  description: string;
  prefill_params: Record<string, string>;
}

export interface IdentifiedIssue {
  issue_type: string;
  issue_label: string;
  confidence: string;
  description: string;
  related_claim_types: string[];
  tools: ToolRecommendation[];
  has_deadline_urgency: boolean;
}

export interface IntakeResult {
  identified_issues: IdentifiedIssue[];
  is_government_employee: boolean;
  employment_status: string;
  summary: string;
  disclaimer: string;
}

// ── Questions ────────────────────────────────────────────────────────

const QUESTIONS: IntakeQuestion[] = [
  {
    question_id: "situation",
    question_text: "Which of these best describes your situation?",
    help_text: "Choose the option that most closely matches what happened.",
    allow_multiple: false,
    show_if: null,
    options: [
      {
        key: "not_paid",
        label: "I wasn't paid correctly",
        help_text: "Missing wages, overtime, or final paycheck issues",
      },
      {
        key: "treated_unfairly",
        label: "I was treated unfairly",
        help_text: "Discrimination, harassment, or denied leave",
      },
      {
        key: "fired_laid_off",
        label: "I was fired or laid off",
        help_text: "Termination you believe was unjust or illegal",
      },
      {
        key: "unsafe_conditions",
        label: "My workplace is unsafe",
        help_text: "Health hazards, safety violations, or dangerous conditions",
      },
      {
        key: "benefits_issue",
        label: "I need help with benefits",
        help_text: "Unemployment, disability, or family leave benefits",
      },
      {
        key: "reported_problem",
        label: "I reported a problem and faced consequences",
        help_text: "Retaliation for whistleblowing or complaints",
      },
    ],
  },
  {
    question_id: "pay_details",
    question_text: "What is the pay issue?",
    help_text: "Select the option that best describes your pay problem.",
    allow_multiple: false,
    show_if: ["not_paid"],
    options: [
      {
        key: "pay_not_received",
        label: "I didn't receive wages I earned",
        help_text: "Missing regular pay, overtime, or final paycheck",
      },
      {
        key: "pay_misclassified",
        label:
          "I'm classified as an independent contractor but should be an employee",
        help_text: "Your employer treats you as 1099 instead of W-2",
      },
      {
        key: "pay_breaks_denied",
        label: "I'm not getting my meal or rest breaks",
        help_text: "Denied or interrupted required break periods",
      },
      {
        key: "pay_na",
        label: "Not sure / other pay issue",
        help_text: "",
      },
    ],
  },
  {
    question_id: "unfair_details",
    question_text: "How were you treated unfairly?",
    help_text: "Select the option that best describes what happened.",
    allow_multiple: false,
    show_if: ["treated_unfairly"],
    options: [
      {
        key: "unfair_protected_class",
        label:
          "Because of my race, gender, age, disability, or other protected characteristic",
        help_text: "Treatment based on who you are",
      },
      {
        key: "unfair_hostile_env",
        label: "Ongoing harassment or hostile work environment",
        help_text: "Repeated unwelcome conduct that is severe or pervasive",
      },
      {
        key: "unfair_leave_denied",
        label: "I was denied family or medical leave",
        help_text: "FMLA/CFRA leave request was denied or punished",
      },
      {
        key: "unfair_na",
        label: "Not sure / other unfair treatment",
        help_text: "",
      },
    ],
  },
  {
    question_id: "retaliation",
    question_text:
      "Did any of these problems happen after you complained, reported a violation, or exercised a legal right?",
    help_text:
      "Retaliation is when an employer punishes you for protected activity.",
    allow_multiple: false,
    show_if: null,
    options: [
      {
        key: "retaliation_yes",
        label: "Yes, I think it was retaliation",
        help_text: "The problem started or got worse after you spoke up",
      },
      {
        key: "retaliation_no",
        label: "No, or I'm not sure",
        help_text: "",
      },
    ],
  },
  {
    question_id: "reported_what",
    question_text: "What did you complain about or report?",
    help_text: "Select the option closest to what you reported.",
    allow_multiple: false,
    show_if: ["retaliation_yes"],
    options: [
      {
        key: "reported_safety",
        label: "Unsafe working conditions",
        help_text: "Health or safety violations",
      },
      {
        key: "reported_pay_violation",
        label: "Pay or wage violations",
        help_text: "Unpaid wages, missing breaks, etc.",
      },
      {
        key: "reported_discrimination",
        label: "Discrimination or harassment",
        help_text: "Unfair treatment based on protected characteristics",
      },
      {
        key: "reported_legal_violation",
        label: "Other illegal activity",
        help_text: "Fraud, law violations, or other misconduct",
      },
      {
        key: "reported_na",
        label: "Not sure / other",
        help_text: "",
      },
    ],
  },
  {
    question_id: "employment_status",
    question_text: "What is your current employment status?",
    help_text: "This affects which remedies and deadlines apply.",
    allow_multiple: false,
    show_if: null,
    options: [
      {
        key: "status_still_employed",
        label: "I still work there",
        help_text: "You are currently employed at this job",
      },
      {
        key: "status_terminated",
        label: "I was fired or laid off",
        help_text: "Your employer ended your employment",
      },
      {
        key: "status_quit",
        label: "I quit",
        help_text: "You left the job voluntarily",
      },
    ],
  },
  {
    question_id: "employer_type",
    question_text: "What type of employer do you work for?",
    help_text: "Government employees have different filing requirements.",
    allow_multiple: false,
    show_if: null,
    options: [
      {
        key: "employer_private",
        label: "Private company",
        help_text: "Most businesses, non-profits, etc.",
      },
      {
        key: "employer_government",
        label: "Government agency",
        help_text: "City, county, state, or federal government",
      },
      {
        key: "employer_unsure",
        label: "Not sure",
        help_text: "",
      },
    ],
  },
  {
    question_id: "benefits_needed",
    question_text:
      "Do you need to apply for any of these benefits right now?",
    help_text: "Select all that apply. These are separate from your employment claim.",
    allow_multiple: true,
    show_if: null,
    options: [
      {
        key: "need_unemployment",
        label: "Unemployment insurance",
        help_text: "If you lost your job and need income",
      },
      {
        key: "need_disability",
        label: "State disability insurance (SDI)",
        help_text: "If you can't work due to illness or injury",
      },
      {
        key: "need_family_leave",
        label: "Paid family leave",
        help_text: "To bond with a new child or care for a family member",
      },
      {
        key: "need_none",
        label: "None of these",
        help_text: "",
      },
    ],
  },
];

// ── Signal map: answer key → { issue_type: weight } ─────────────────

const SIGNAL_MAP: Record<string, Record<string, number>> = {
  not_paid: { unpaid_wages: 1.0, meal_rest_breaks: 0.3, misclassification: 0.3 },
  treated_unfairly: { discrimination: 0.5, harassment: 0.5 },
  fired_laid_off: { wrongful_termination: 1.0 },
  unsafe_conditions: { workplace_safety: 1.0 },
  benefits_issue: {
    unemployment_benefits: 0.5,
    disability_insurance: 0.5,
    paid_family_leave: 0.5,
  },
  reported_problem: { retaliation: 1.0, whistleblower: 0.5 },
  pay_not_received: { unpaid_wages: 1.0 },
  pay_misclassified: { misclassification: 1.0, unpaid_wages: 0.5 },
  pay_breaks_denied: { meal_rest_breaks: 1.0 },
  pay_na: {},
  unfair_protected_class: { discrimination: 1.0 },
  unfair_hostile_env: { harassment: 1.0 },
  unfair_leave_denied: { family_medical_leave: 1.0 },
  unfair_na: {},
  retaliation_yes: { retaliation: 1.0 },
  retaliation_no: {},
  reported_safety: { workplace_safety: 0.5, whistleblower: 1.0 },
  reported_pay_violation: { unpaid_wages: 0.3, whistleblower: 0.5 },
  reported_discrimination: { discrimination: 0.3, whistleblower: 0.5 },
  reported_legal_violation: { whistleblower: 1.0 },
  reported_na: {},
  status_still_employed: {},
  status_terminated: { wrongful_termination: 0.3 },
  status_quit: {},
  employer_private: {},
  employer_government: {},
  employer_unsure: {},
  need_unemployment: { unemployment_benefits: 1.0 },
  need_disability: { disability_insurance: 1.0 },
  need_family_leave: { paid_family_leave: 1.0, family_medical_leave: 0.5 },
  need_none: {},
};

// ── Issue type labels ────────────────────────────────────────────────

const ISSUE_TYPE_LABELS: Record<string, string> = {
  unpaid_wages: "Unpaid Wages / Wage Theft",
  discrimination: "Discrimination (Race, Gender, Age, Disability, etc.)",
  harassment: "Harassment / Hostile Work Environment",
  wrongful_termination: "Wrongful Termination",
  retaliation: "Retaliation for Exercising Rights",
  family_medical_leave: "Family / Medical Leave Violations",
  workplace_safety: "Workplace Safety / Health Hazards",
  misclassification: "Worker Misclassification (1099 vs W-2)",
  unemployment_benefits: "Unemployment Insurance Benefits",
  disability_insurance: "State Disability Insurance (SDI)",
  paid_family_leave: "Paid Family Leave (PFL)",
  meal_rest_breaks: "Meal / Rest Break Violations",
  whistleblower: "Whistleblower Protections",
};

// ── Issue descriptions ───────────────────────────────────────────────

const ISSUE_DESCRIPTIONS: Record<string, string> = {
  unpaid_wages:
    "Your employer may owe you unpaid wages. California law requires timely payment of all earned wages.",
  discrimination:
    "You may have experienced illegal workplace discrimination based on a protected characteristic under California's FEHA.",
  harassment:
    "You may have a claim for workplace harassment or hostile work environment under California law.",
  wrongful_termination:
    "Your termination may have violated California law or public policy.",
  retaliation:
    "You may have been retaliated against for exercising a protected legal right.",
  family_medical_leave:
    "You may have been denied family or medical leave rights under CFRA/FMLA.",
  workplace_safety:
    "Your workplace may have unsafe conditions that violate Cal/OSHA standards.",
  misclassification:
    "You may be misclassified as an independent contractor when you should be treated as an employee.",
  unemployment_benefits:
    "You may be eligible for unemployment insurance benefits through EDD.",
  disability_insurance:
    "You may be eligible for State Disability Insurance (SDI) benefits through EDD.",
  paid_family_leave:
    "You may be eligible for Paid Family Leave (PFL) benefits through EDD.",
  meal_rest_breaks:
    "Your employer may owe you premium pay for missed meal or rest breaks.",
  whistleblower:
    "You may have whistleblower protections for reporting illegal activity at your workplace.",
};

// ── Issue to claim type mapping ──────────────────────────────────────

const ISSUE_TO_CLAIM: Record<string, string[]> = {
  unpaid_wages: ["wage_theft"],
  discrimination: ["feha_discrimination"],
  harassment: ["feha_discrimination"],
  wrongful_termination: ["wrongful_termination"],
  retaliation: ["retaliation_whistleblower"],
  family_medical_leave: ["cfra_family_leave"],
  workplace_safety: [],
  misclassification: ["misclassification"],
  unemployment_benefits: [],
  disability_insurance: [],
  paid_family_leave: [],
  meal_rest_breaks: ["wage_theft"],
  whistleblower: ["retaliation_whistleblower"],
};

// ── Issue to incident type mapping ───────────────────────────────────

const ISSUE_TO_INCIDENT: Record<string, string | null> = {
  unpaid_wages: "unpaid_wages",
  discrimination: "discrimination",
  harassment: "harassment",
  wrongful_termination: "wrongful_termination",
  retaliation: "retaliation",
  family_medical_leave: "family_medical_leave",
  workplace_safety: "workplace_safety",
  misclassification: "misclassification",
  unemployment_benefits: null,
  disability_insurance: null,
  paid_family_leave: null,
  meal_rest_breaks: "meal_rest_breaks",
  whistleblower: "whistleblower",
};

// ── Wage issues ──────────────────────────────────────────────────────

const WAGE_ISSUES = new Set([
  "unpaid_wages",
  "meal_rest_breaks",
  "misclassification",
]);

// ── Score threshold ──────────────────────────────────────────────────

const SCORE_THRESHOLD = 0.8;

// ── Disclaimer ───────────────────────────────────────────────────────

const DISCLAIMER =
  "This questionnaire provides general guidance to help you identify " +
  "potential employment law issues based on your answers. It is not legal " +
  "advice, and it does not create an attorney-client relationship. " +
  "Employment law is complex, and your specific facts may lead to " +
  "different conclusions. Consult a licensed California employment " +
  "attorney for advice about your specific situation.";

// ── Tool label mapping ───────────────────────────────────────────────

const TOOL_LABELS: Record<string, string> = {
  agency_routing: "Agency Routing Guide",
  deadline_calculator: "Deadline Calculator",
  incident_docs: "Incident Documentation",
  unpaid_wages_calculator: "Unpaid Wages Calculator",
};

// ── Build tool recommendations for an issue ──────────────────────────

function buildToolRecommendations(
  issueType: string,
  claimTypes: string[],
  incidentType: string | null
): ToolRecommendation[] {
  const tools: ToolRecommendation[] = [];

  // 1. Always: agency routing
  tools.push({
    tool_name: "agency_routing",
    tool_label: TOOL_LABELS["agency_routing"],
    tool_path: "/tools/agency-routing",
    description:
      "Find which government agency handles your complaint and how to file.",
    prefill_params: { issue_type: issueType },
  });

  // 2. If claim types exist: deadline calculator
  if (claimTypes.length > 0) {
    tools.push({
      tool_name: "deadline_calculator",
      tool_label: TOOL_LABELS["deadline_calculator"],
      tool_path: "/tools/deadline-calculator",
      description:
        "Check your filing deadlines to make sure you don't miss any cutoff dates.",
      prefill_params: { claim_type: claimTypes[0] },
    });
  }

  // 3. If incident type mapping exists: incident documentation
  if (incidentType) {
    tools.push({
      tool_name: "incident_docs",
      tool_label: TOOL_LABELS["incident_docs"],
      tool_path: "/tools/incident-docs",
      description:
        "Document what happened while details are fresh. All data stays in your browser.",
      prefill_params: { incident_type: incidentType },
    });
  }

  // 4. If wage issue: unpaid wages calculator
  if (WAGE_ISSUES.has(issueType)) {
    tools.push({
      tool_name: "unpaid_wages_calculator",
      tool_label: TOOL_LABELS["unpaid_wages_calculator"],
      tool_path: "/tools/unpaid-wages-calculator",
      description:
        "Estimate how much you may be owed including penalties and interest.",
      prefill_params: {},
    });
  }

  return tools;
}

// ── Build summary text ───────────────────────────────────────────────

function buildSummary(issues: IdentifiedIssue[]): string {
  if (issues.length === 0) {
    return (
      "Based on your answers, we couldn't identify a specific employment " +
      "law issue. Consider speaking with a California employment attorney " +
      "for personalized guidance."
    );
  }

  if (issues.length === 1) {
    return (
      `Based on your answers, your situation most closely matches: ` +
      `${issues[0].issue_label}. Review the recommended tools below ` +
      `to take the next step.`
    );
  }

  const labels = issues.map((i) => i.issue_label).join(", ");
  return (
    `Based on your answers, your situation may involve multiple issues: ` +
    `${labels}. Review the recommended tools below for each issue.`
  );
}

// ── Public API ───────────────────────────────────────────────────────

/**
 * Return the full list of intake questions.
 */
export function getQuestions(): IntakeQuestion[] {
  // Return a deep copy so callers cannot mutate internal state
  return JSON.parse(JSON.stringify(QUESTIONS));
}

/**
 * Evaluate a flat list of answer keys and produce an IntakeResult
 * with identified issues, tool recommendations, and summary text.
 */
export function evaluateIntake(answers: string[]): IntakeResult {
  // 1. Accumulate scores from signal map
  const scores: Record<string, number> = {};
  for (const key of answers) {
    const signals = SIGNAL_MAP[key];
    if (!signals) continue;
    for (const [issueType, weight] of Object.entries(signals)) {
      scores[issueType] = (scores[issueType] ?? 0) + weight;
    }
  }

  // 2. Detect government employee
  const isGovernmentEmployee = answers.includes("employer_government");

  // 3. Detect employment status
  let employmentStatus = "still_employed";
  if (answers.includes("status_terminated")) {
    employmentStatus = "terminated";
  } else if (answers.includes("status_quit")) {
    employmentStatus = "quit";
  }

  // 4. Filter issues above threshold, sorted by score descending
  const qualifiedIssues = Object.entries(scores)
    .filter(([, score]) => score >= SCORE_THRESHOLD)
    .sort((a, b) => b[1] - a[1]);

  // 5. Build identified issues
  const identifiedIssues: IdentifiedIssue[] = qualifiedIssues.map(
    ([issueType, score]) => {
      const confidence = score >= 1.5 ? "high" : "medium";
      const claimTypes = [...(ISSUE_TO_CLAIM[issueType] ?? [])];

      // 6. If government employee and claim types exist, add government_employee
      if (isGovernmentEmployee && claimTypes.length > 0) {
        claimTypes.push("government_employee");
      }

      const incidentType = ISSUE_TO_INCIDENT[issueType] ?? null;
      const tools = buildToolRecommendations(issueType, claimTypes, incidentType);

      // 7. has_deadline_urgency = claim types list is not empty
      const hasDeadlineUrgency = claimTypes.length > 0;

      return {
        issue_type: issueType,
        issue_label: ISSUE_TYPE_LABELS[issueType] ?? issueType,
        confidence,
        description: ISSUE_DESCRIPTIONS[issueType] ?? "",
        related_claim_types: claimTypes,
        tools,
        has_deadline_urgency: hasDeadlineUrgency,
      };
    }
  );

  // 8. Build summary
  const summary = buildSummary(identifiedIssues);

  return {
    identified_issues: identifiedIssues,
    is_government_employee: isGovernmentEmployee,
    employment_status: employmentStatus,
    summary,
    disclaimer: DISCLAIMER,
  };
}
