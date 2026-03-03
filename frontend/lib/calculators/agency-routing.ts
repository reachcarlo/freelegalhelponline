// ── Agency Routing Guide ────────────────────────────────────────────
// Client-side port of the Python agency routing logic.
// No network requests — all data is embedded.

// ── Types ───────────────────────────────────────────────────────────

export interface AgencyRecommendationInfo {
  agency_name: string;
  agency_acronym: string;
  agency_description: string;
  agency_handles: string;
  portal_url: string;
  phone: string;
  filing_methods: string[];
  process_overview: string;
  typical_timeline: string;
  priority: "prerequisite" | "primary" | "alternative";
  reason: string;
  what_to_file: string;
  notes: string;
  related_claim_type: string | null;
}

export interface AgencyRoutingResponse {
  issue_type: string;
  issue_type_label: string;
  is_government_employee: boolean;
  recommendations: AgencyRecommendationInfo[];
  disclaimer: string;
}

// ── Static Data ─────────────────────────────────────────────────────

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

interface AgencyInfo {
  name: string;
  acronym: string;
  description: string;
  handles: string;
  portal_url: string;
  phone: string;
  filing_methods: string[];
  process_overview: string;
  typical_timeline: string;
}

const AGENCIES: Record<string, AgencyInfo> = {
  dlse: {
    name: "Division of Labor Standards Enforcement",
    acronym: "DLSE",
    description:
      "The Labor Commissioner's Office enforces California wage and hour laws, investigates retaliation complaints, and resolves wage disputes.",
    handles:
      "Wage claims, meal/rest break violations, retaliation, misclassification",
    portal_url: "https://www.dir.ca.gov/dlse/",
    phone: "(844) 522-6734",
    filing_methods: ["Online", "Mail", "In person at local office"],
    process_overview:
      "File a wage claim or retaliation complaint. DLSE investigates, schedules a settlement conference, and may hold a formal hearing.",
    typical_timeline:
      "3-6 months for investigation; hearing within 12 months",
  },
  crd: {
    name: "Civil Rights Department",
    acronym: "CRD",
    description:
      "The Civil Rights Department enforces California's civil rights laws, including the Fair Employment and Housing Act (FEHA).",
    handles:
      "Discrimination, harassment, retaliation, family/medical leave violations",
    portal_url: "https://calcivilrights.ca.gov/complaintprocess/",
    phone: "(800) 884-1684",
    filing_methods: ["Online portal", "Mail", "Phone intake"],
    process_overview:
      "File a complaint online or by mail. CRD investigates, may attempt mediation, and issues a right-to-sue notice if unresolved.",
    typical_timeline:
      "1-3 months for initial review; 12-18 months for full investigation",
  },
  edd: {
    name: "Employment Development Department",
    acronym: "EDD",
    description:
      "EDD administers unemployment insurance, disability insurance, and paid family leave programs for California workers.",
    handles:
      "Unemployment insurance, state disability insurance, paid family leave",
    portal_url: "https://edd.ca.gov/",
    phone: "(800) 300-5616",
    filing_methods: ["Online (UI Online / SDI Online)", "Phone", "Mail"],
    process_overview:
      "File a claim online or by phone. EDD reviews eligibility, may schedule a phone interview, and issues a determination.",
    typical_timeline:
      "2-4 weeks for initial determination; appeals take 4-8 weeks",
  },
  cal_osha: {
    name: "Division of Occupational Safety and Health",
    acronym: "Cal/OSHA",
    description:
      "Cal/OSHA enforces workplace health and safety standards to protect California workers.",
    handles: "Workplace safety complaints, health hazards, safety retaliation",
    portal_url: "https://www.dir.ca.gov/dosh/",
    phone: "(844) 522-6734",
    filing_methods: ["Online", "Phone", "Mail", "In person"],
    process_overview:
      "File a safety complaint (can be anonymous). Cal/OSHA inspects the workplace, issues citations for violations, and requires corrective action.",
    typical_timeline:
      "1-5 days for imminent hazards; 14-30 days for standard complaints",
  },
  lwda: {
    name: "Labor & Workforce Development Agency",
    acronym: "LWDA",
    description:
      "LWDA oversees California labor agencies and administers the Private Attorneys General Act (PAGA) notice process.",
    handles: "PAGA notices for labor code violations",
    portal_url:
      "https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
    phone: "",
    filing_methods: ["Online PAGA notice submission"],
    process_overview:
      "Submit a PAGA notice to LWDA and your employer. After 65 days, if LWDA does not investigate, you may file a civil action.",
    typical_timeline: "65-day waiting period after PAGA notice",
  },
  eeoc: {
    name: "Equal Employment Opportunity Commission",
    acronym: "EEOC",
    description:
      "The EEOC enforces federal anti-discrimination laws, including Title VII, the ADA, and the ADEA.",
    handles:
      "Federal discrimination, harassment, and retaliation complaints",
    portal_url: "https://www.eeoc.gov/filing-charge-discrimination",
    phone: "(800) 669-4000",
    filing_methods: ["Online portal", "In person at local office", "Mail"],
    process_overview:
      "File a charge of discrimination. EEOC investigates, may attempt conciliation, and issues a right-to-sue letter if unresolved.",
    typical_timeline:
      "6-10 months for investigation; 180 days for right-to-sue",
  },
  calhr: {
    name: "California Department of Human Resources",
    acronym: "CalHR",
    description:
      "CalHR manages the state's human resources programs and handles complaints from state government employees.",
    handles:
      "State employee grievances, EEO complaints, classification disputes",
    portal_url: "https://www.calhr.ca.gov/",
    phone: "(866) 225-4728",
    filing_methods: ["Internal grievance process", "Written complaint"],
    process_overview:
      "File an internal complaint through your department's EEO office or CalHR. Must exhaust administrative remedies before filing with external agencies.",
    typical_timeline: "30-90 days for internal review",
  },
  superior_court: {
    name: "California Superior Court",
    acronym: "Court",
    description:
      "California Superior Courts hear civil lawsuits, including employment disputes, wrongful termination, and discrimination cases.",
    handles: "Civil lawsuits for employment disputes",
    portal_url: "https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
    phone: "",
    filing_methods: ["In person at courthouse", "E-filing (select counties)"],
    process_overview:
      "File a civil complaint in the appropriate Superior Court. Case proceeds through discovery, possible settlement, and trial.",
    typical_timeline:
      "12-24 months to trial; small claims heard within 30-70 days",
  },
};

// Each routing rule: [agency_key, priority, reason, what_to_file, notes, related_claim_type]
type RoutingRule = [
  string,
  "prerequisite" | "primary" | "alternative",
  string,
  string,
  string,
  string | null,
];

const ROUTING_RULES: Record<string, RoutingRule[]> = {
  unpaid_wages: [
    [
      "dlse",
      "primary",
      "DLSE is the primary agency for wage claims in California.",
      "Wage claim (DLSE Form 1)",
      "",
      "wage_theft",
    ],
    [
      "superior_court",
      "alternative",
      "You can file a civil lawsuit instead of or after a DLSE claim.",
      "Civil complaint for unpaid wages",
      "Consider small claims court for amounts under $12,500.",
      "wage_theft",
    ],
    [
      "lwda",
      "alternative",
      "File a PAGA notice to pursue penalties on behalf of yourself and coworkers.",
      "PAGA notice to LWDA",
      "Requires 65-day waiting period before filing suit.",
      "wage_theft",
    ],
  ],
  discrimination: [
    [
      "crd",
      "primary",
      "CRD enforces California's Fair Employment and Housing Act (FEHA), the primary state anti-discrimination law.",
      "Pre-complaint inquiry or formal complaint",
      "",
      "feha_discrimination",
    ],
    [
      "eeoc",
      "alternative",
      "The EEOC handles federal discrimination claims. CRD and EEOC have a work-sharing agreement, so filing with one can cross-file with the other.",
      "Charge of discrimination",
      "300-day filing deadline from the discriminatory act.",
      "feha_discrimination",
    ],
    [
      "superior_court",
      "alternative",
      "File a civil lawsuit after obtaining a right-to-sue notice from CRD.",
      "Civil complaint for discrimination",
      "Must first file with CRD and obtain a right-to-sue letter.",
      "feha_discrimination",
    ],
  ],
  harassment: [
    [
      "crd",
      "primary",
      "CRD handles harassment complaints under FEHA, including sexual harassment and hostile work environment.",
      "Pre-complaint inquiry or formal complaint",
      "",
      "feha_discrimination",
    ],
    [
      "eeoc",
      "alternative",
      "The EEOC handles federal harassment claims under Title VII.",
      "Charge of discrimination (harassment)",
      "300-day filing deadline.",
      "feha_discrimination",
    ],
    [
      "superior_court",
      "alternative",
      "File a civil lawsuit after obtaining a right-to-sue notice.",
      "Civil complaint for harassment",
      "Must first file with CRD and obtain a right-to-sue letter.",
      "feha_discrimination",
    ],
  ],
  wrongful_termination: [
    [
      "superior_court",
      "primary",
      "Wrongful termination lawsuits are typically filed directly in court.",
      "Civil complaint for wrongful termination",
      "May be based on public policy, breach of contract, or discrimination.",
      "wrongful_termination",
    ],
    [
      "crd",
      "alternative",
      "If termination was discriminatory, file with CRD first.",
      "Pre-complaint inquiry or formal complaint",
      "Only applies if termination was based on a protected characteristic.",
      "wrongful_termination",
    ],
  ],
  retaliation: [
    [
      "dlse",
      "primary",
      "DLSE investigates retaliation complaints for exercising labor rights.",
      "Retaliation complaint (Labor Code \u00A798.6)",
      "6-month deadline from the retaliatory act.",
      "retaliation_whistleblower",
    ],
    [
      "superior_court",
      "alternative",
      "File a civil lawsuit for retaliation.",
      "Civil complaint for retaliation",
      "",
      "retaliation_whistleblower",
    ],
    [
      "crd",
      "alternative",
      "If retaliation is related to a FEHA-protected activity, file with CRD.",
      "Pre-complaint inquiry or formal complaint",
      "Applies when retaliation is for opposing discrimination or harassment.",
      "retaliation_whistleblower",
    ],
  ],
  family_medical_leave: [
    [
      "crd",
      "primary",
      "CRD enforces CFRA (California Family Rights Act) and handles family/medical leave violations.",
      "Pre-complaint inquiry or formal complaint",
      "",
      "cfra_family_leave",
    ],
    [
      "eeoc",
      "alternative",
      "The EEOC handles federal FMLA violations.",
      "Charge of discrimination (FMLA interference)",
      "For federal FMLA claims; California CFRA claims go through CRD.",
      "cfra_family_leave",
    ],
  ],
  workplace_safety: [
    [
      "cal_osha",
      "primary",
      "Cal/OSHA enforces workplace health and safety standards.",
      "Safety complaint (can be filed anonymously)",
      "Complaints can be anonymous. Cal/OSHA must inspect within set timeframes.",
      null,
    ],
    [
      "dlse",
      "alternative",
      "If you were retaliated against for reporting safety concerns, file with DLSE.",
      "Retaliation complaint",
      "Separate from the safety complaint itself.",
      null,
    ],
  ],
  misclassification: [
    [
      "dlse",
      "primary",
      "DLSE investigates worker misclassification and can recover unpaid wages and benefits.",
      "Wage claim or misclassification complaint",
      "",
      "misclassification",
    ],
    [
      "superior_court",
      "alternative",
      "File a civil lawsuit for damages from misclassification.",
      "Civil complaint for misclassification",
      "",
      "misclassification",
    ],
    [
      "lwda",
      "alternative",
      "File a PAGA notice for misclassification violations.",
      "PAGA notice to LWDA",
      "Requires 65-day waiting period before filing suit.",
      "misclassification",
    ],
  ],
  unemployment_benefits: [
    [
      "edd",
      "primary",
      "EDD administers unemployment insurance benefits in California.",
      "Unemployment insurance claim",
      "File online at UI Online for fastest processing.",
      null,
    ],
  ],
  disability_insurance: [
    [
      "edd",
      "primary",
      "EDD administers State Disability Insurance (SDI) for workers unable to work due to non-work-related illness or injury.",
      "SDI claim",
      "File online at SDI Online. Requires medical certification.",
      null,
    ],
  ],
  paid_family_leave: [
    [
      "edd",
      "primary",
      "EDD administers Paid Family Leave (PFL) for bonding with a new child or caring for a seriously ill family member.",
      "PFL claim",
      "File online at SDI Online. Provides up to 8 weeks of partial wage replacement.",
      null,
    ],
  ],
  meal_rest_breaks: [
    [
      "dlse",
      "primary",
      "DLSE enforces meal and rest break requirements under California labor law.",
      "Wage claim for meal/rest break violations",
      "Employees are entitled to premium pay for missed breaks.",
      "wage_theft",
    ],
    [
      "lwda",
      "alternative",
      "File a PAGA notice for meal/rest break violations on behalf of coworkers.",
      "PAGA notice to LWDA",
      "Requires 65-day waiting period before filing suit.",
      "wage_theft",
    ],
    [
      "superior_court",
      "alternative",
      "File a civil lawsuit for meal/rest break violations.",
      "Civil complaint for meal/rest break violations",
      "",
      "wage_theft",
    ],
  ],
  whistleblower: [
    [
      "dlse",
      "primary",
      "DLSE handles whistleblower retaliation complaints under Labor Code \u00A71102.5.",
      "Retaliation/whistleblower complaint",
      "",
      "retaliation_whistleblower",
    ],
    [
      "superior_court",
      "alternative",
      "File a whistleblower retaliation lawsuit in court.",
      "Civil complaint for whistleblower retaliation",
      "",
      "retaliation_whistleblower",
    ],
    [
      "cal_osha",
      "alternative",
      "If you reported workplace safety issues, Cal/OSHA also investigates whistleblower retaliation.",
      "Safety retaliation complaint",
      "Applies specifically to health and safety whistleblowing.",
      "retaliation_whistleblower",
    ],
  ],
};

// Issue types where government employees must first go through CalHR
const GOV_CALHR_PREREQUISITE: Set<string> = new Set([
  "unpaid_wages",
  "discrimination",
  "harassment",
  "retaliation",
  "family_medical_leave",
  "meal_rest_breaks",
]);

// Issue types where government employees must first file a tort claim
const GOV_TORT_PREREQUISITE: Set<string> = new Set([
  "wrongful_termination",
  "whistleblower",
]);

const DISCLAIMER =
  "This routing guide provides general information about California government agencies that handle employment complaints. It is not legal advice. Filing requirements, deadlines, and procedures may vary depending on your specific situation, employer type, and the nature of your claim. Consult a licensed California employment attorney for advice about your specific situation.";

// ── Priority sort order ─────────────────────────────────────────────

const PRIORITY_ORDER: Record<string, number> = {
  prerequisite: 0,
  primary: 1,
  alternative: 2,
};

// ── Helper ──────────────────────────────────────────────────────────

function buildRecommendation(
  rule: RoutingRule,
): AgencyRecommendationInfo {
  const [agencyKey, priority, reason, whatToFile, notes, relatedClaimType] =
    rule;
  const agency = AGENCIES[agencyKey];
  return {
    agency_name: agency.name,
    agency_acronym: agency.acronym,
    agency_description: agency.description,
    agency_handles: agency.handles,
    portal_url: agency.portal_url,
    phone: agency.phone,
    filing_methods: agency.filing_methods,
    process_overview: agency.process_overview,
    typical_timeline: agency.typical_timeline,
    priority,
    reason,
    what_to_file: whatToFile,
    notes,
    related_claim_type: relatedClaimType,
  };
}

// ── Main export ─────────────────────────────────────────────────────

export function getAgencyRouting(
  issueType: string,
  isGovernmentEmployee: boolean = false,
): AgencyRoutingResponse {
  const label = ISSUE_TYPE_LABELS[issueType];
  if (!label) {
    throw new Error(
      `Unknown issue type: ${issueType}. Valid types: ${Object.keys(ISSUE_TYPE_LABELS).join(", ")}`,
    );
  }

  const rules = ROUTING_RULES[issueType];
  if (!rules) {
    throw new Error(`No routing rules found for issue type: ${issueType}`);
  }

  // Build base recommendations from routing rules
  const recommendations: AgencyRecommendationInfo[] = rules.map(buildRecommendation);

  // Government employee prerequisite injection
  if (isGovernmentEmployee) {
    if (GOV_CALHR_PREREQUISITE.has(issueType)) {
      const calhr = AGENCIES.calhr;
      recommendations.unshift({
        agency_name: calhr.name,
        agency_acronym: calhr.acronym,
        agency_description: calhr.description,
        agency_handles: calhr.handles,
        portal_url: calhr.portal_url,
        phone: calhr.phone,
        filing_methods: calhr.filing_methods,
        process_overview: calhr.process_overview,
        typical_timeline: calhr.typical_timeline,
        priority: "prerequisite",
        reason:
          "As a government employee, you must first exhaust internal administrative remedies through CalHR or your department's EEO office before filing with external agencies.",
        what_to_file: "Internal grievance or EEO complaint",
        notes:
          "This step is required before filing with external agencies. Keep records of all submissions and responses.",
        related_claim_type: null,
      });
    } else if (GOV_TORT_PREREQUISITE.has(issueType)) {
      const court = AGENCIES.superior_court;
      recommendations.unshift({
        agency_name: court.name,
        agency_acronym: court.acronym,
        agency_description: court.description,
        agency_handles: court.handles,
        portal_url: court.portal_url,
        phone: court.phone,
        filing_methods: court.filing_methods,
        process_overview:
          "Before suing a government employer, you must file a government tort claim within 6 months of the incident.",
        typical_timeline:
          "Government must respond within 45 days; deemed rejected if no response",
        priority: "prerequisite",
        reason:
          "As a government employee, you must file a government tort claim before filing a lawsuit against your employer.",
        what_to_file: "Government tort claim (Government Code \u00A7910)",
        notes:
          "Strict 6-month deadline. Failure to file a tort claim first will result in your lawsuit being dismissed.",
        related_claim_type: null,
      });
    }

    // Sort: prerequisite first, then primary, then alternative
    recommendations.sort(
      (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority],
    );
  }

  return {
    issue_type: issueType,
    issue_type_label: label,
    is_government_employee: isGovernmentEmployee,
    recommendations,
    disclaimer: DISCLAIMER,
  };
}
