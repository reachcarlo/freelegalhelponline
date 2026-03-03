/**
 * Incident documentation helper — client-side port of the Python tool.
 *
 * Provides structured guidance for documenting 10 workplace incident types
 * with common fields, type-specific fields, prompts, evidence checklists,
 * related claim types, and legal tips.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface DocumentationFieldInfo {
  name: string;
  label: string;
  field_type:
    | "text"
    | "textarea"
    | "date"
    | "time"
    | "number"
    | "select"
    | "boolean";
  placeholder: string;
  required: boolean;
  help_text: string;
  options: string[];
}

export interface EvidenceItemInfo {
  description: string;
  importance: "critical" | "recommended" | "optional";
  tip: string;
}

export interface IncidentDocResponse {
  incident_type: string;
  incident_type_label: string;
  description: string;
  common_fields: DocumentationFieldInfo[];
  specific_fields: DocumentationFieldInfo[];
  prompts: string[];
  evidence_checklist: EvidenceItemInfo[];
  related_claim_types: string[];
  legal_tips: string[];
  disclaimer: string;
}

// ── Helpers ──────────────────────────────────────────────────────────

function field(
  overrides: Partial<DocumentationFieldInfo> & {
    name: string;
    label: string;
    field_type: DocumentationFieldInfo["field_type"];
  }
): DocumentationFieldInfo {
  return {
    placeholder: "",
    required: false,
    help_text: "",
    options: [],
    ...overrides,
  };
}

function evidence(
  importance: EvidenceItemInfo["importance"],
  description: string,
  tip: string = ""
): EvidenceItemInfo {
  return { description, importance, tip };
}

// ── Constants ────────────────────────────────────────────────────────

const DISCLAIMER =
  "This tool helps you create a personal record of workplace incidents. " +
  "It is NOT a legal document and does not constitute legal advice. " +
  "Your data is stored only in your browser and is never sent to our servers. " +
  "Consult a licensed California employment attorney for advice about your specific situation.";

const COMMON_FIELDS: DocumentationFieldInfo[] = [
  field({
    name: "incident_date",
    label: "Date of Incident",
    field_type: "date",
    required: true,
    help_text: "When did this incident occur?",
  }),
  field({
    name: "incident_time",
    label: "Time of Incident",
    field_type: "time",
    help_text: "Approximate time, if you remember.",
  }),
  field({
    name: "location",
    label: "Location",
    field_type: "text",
    placeholder: "e.g., Main office, 3rd floor break room",
    required: true,
    help_text: "Where did this happen?",
  }),
  field({
    name: "witnesses",
    label: "Witnesses",
    field_type: "textarea",
    placeholder:
      "Names and contact info of anyone who saw or heard what happened",
    help_text: "List anyone present during the incident.",
  }),
  field({
    name: "narrative",
    label: "What Happened",
    field_type: "textarea",
    placeholder:
      "While details are fresh, write down exactly what happened",
    required: true,
    help_text:
      "Describe the incident in your own words. Include who was involved, what was said, and what actions were taken.",
  }),
  field({
    name: "quotes",
    label: "Exact Words Spoken",
    field_type: "textarea",
    placeholder:
      "Write down any exact words or phrases you remember",
    help_text:
      "Direct quotes are powerful evidence. Record them as precisely as possible.",
  }),
  field({
    name: "employer_response",
    label: "Employer Response",
    field_type: "textarea",
    placeholder: "How did your employer or supervisor respond?",
    help_text:
      "Document any response from management, HR, or supervisors.",
  }),
  field({
    name: "impact",
    label: "Impact on You",
    field_type: "textarea",
    placeholder:
      "How has this affected your work, health, or well-being?",
    help_text: "Describe any emotional, physical, or financial impact.",
  }),
];

// ── Per-incident-type data ───────────────────────────────────────────

interface IncidentGuideData {
  label: string;
  description: string;
  specific_fields: DocumentationFieldInfo[];
  prompts: string[];
  evidence_checklist: EvidenceItemInfo[];
  related_claim_types: string[];
  legal_tips: string[];
}

const INCIDENT_GUIDES: Record<string, IncidentGuideData> = {
  // ── 1. Discrimination ──────────────────────────────────────────────
  discrimination: {
    label: "Discrimination",
    description:
      "Document incidents where you were treated differently or unfavorably because of a protected characteristic such as race, gender, age, disability, religion, or national origin.",
    specific_fields: [
      field({
        name: "protected_characteristic",
        label: "Protected Characteristic",
        field_type: "select",
        required: true,
        options: [
          "Race/Ethnicity",
          "Gender/Sex",
          "Age (40+)",
          "Disability",
          "Religion",
          "National Origin",
          "Sexual Orientation",
          "Gender Identity",
          "Pregnancy",
          "Marital Status",
          "Military/Veteran Status",
          "Other",
        ],
      }),
      field({
        name: "adverse_action",
        label: "Adverse Action",
        field_type: "textarea",
        placeholder: "e.g., denied promotion, reduced hours, terminated",
      }),
      field({
        name: "comparator_treatment",
        label: "Comparator Treatment",
        field_type: "textarea",
        placeholder:
          "Were others outside your protected group treated differently?",
      }),
    ],
    prompts: [
      "What specific comments, actions, or decisions made you believe this was based on your protected characteristic?",
      "Were there other employees in a similar situation who were treated differently? How?",
      "Did you report this to HR or a supervisor? What was their response?",
      "Has there been a pattern of similar treatment, or was this a single incident?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Written communications (emails, texts, memos) showing discriminatory language or decisions",
        "Screenshot and save emails before they can be deleted."
      ),
      evidence(
        "critical",
        "Performance reviews or evaluations (yours and comparators if available)",
        "Keep copies of all reviews, especially positive ones before the adverse action."
      ),
      evidence(
        "recommended",
        "Company policies on the relevant decision (promotion, hiring, etc.)",
        "Check your employee handbook or intranet."
      ),
      evidence(
        "recommended",
        "Witness statements or names of people who observed the treatment"
      ),
      evidence(
        "recommended",
        "Timeline of events showing pattern of differential treatment"
      ),
      evidence(
        "optional",
        "Notes from any meetings with HR or management about the issue"
      ),
    ],
    related_claim_types: ["feha_discrimination"],
    legal_tips: [
      "Under FEHA, California protects more characteristics than federal law. You have 3 years to file a complaint with the Civil Rights Department (CRD).",
      "Document how similarly-situated employees outside your protected group were treated differently \u2014 this 'comparator evidence' is often key to proving discrimination.",
    ],
  },

  // ── 2. Harassment ──────────────────────────────────────────────────
  harassment: {
    label: "Harassment / Hostile Work Environment",
    description:
      "Document incidents of unwelcome conduct based on a protected characteristic that is severe or pervasive enough to create a hostile work environment.",
    specific_fields: [
      field({
        name: "harassment_type",
        label: "Type of Harassment",
        field_type: "select",
        required: true,
        options: [
          "Sexual harassment",
          "Racial harassment",
          "Age-based harassment",
          "Disability-based harassment",
          "Religious harassment",
          "Gender identity harassment",
          "Other protected characteristic",
        ],
      }),
      field({
        name: "frequency",
        label: "Frequency",
        field_type: "select",
        options: [
          "Single incident",
          "Weekly",
          "Daily",
          "Multiple times per day",
          "Ongoing/continuous",
        ],
      }),
      field({
        name: "reported_to_hr",
        label: "Reported to HR",
        field_type: "boolean",
        help_text: "Have you reported this to HR or management?",
      }),
      field({
        name: "hr_response",
        label: "HR Response",
        field_type: "textarea",
        placeholder:
          "What action did HR or management take after your report?",
      }),
    ],
    prompts: [
      "Describe the specific words, gestures, or actions that constitute the harassment.",
      "How often does this happen, and has the behavior escalated over time?",
      "Did you report the behavior to anyone? What happened after you reported it?",
      "Have other employees experienced similar behavior from this person?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Dated log of each incident with specific details (who, what, when, where)",
        "A contemporaneous log \u2014 written at or near the time of each incident \u2014 carries significant weight."
      ),
      evidence(
        "critical",
        "Written complaints to HR or management and their responses",
        "Always submit complaints in writing (email) so you have a record."
      ),
      evidence(
        "critical",
        "Offensive emails, texts, messages, or images",
        "Take screenshots with visible timestamps."
      ),
      evidence(
        "recommended",
        "Names of witnesses who can corroborate incidents"
      ),
      evidence(
        "recommended",
        "Company anti-harassment policy",
        "Document whether the company followed its own policy."
      ),
      evidence(
        "optional",
        "Medical or therapy records showing emotional/physical impact",
        "If the harassment has affected your health, records from your doctor or therapist can support your claim."
      ),
    ],
    related_claim_types: ["feha_discrimination"],
    legal_tips: [
      "Under California law, a single severe incident can constitute harassment \u2014 it does not always need to be a pattern of behavior.",
      "Your employer can be liable if they knew or should have known about the harassment and failed to take prompt corrective action.",
    ],
  },

  // ── 3. Wrongful Termination ────────────────────────────────────────
  wrongful_termination: {
    label: "Wrongful Termination",
    description:
      "Document circumstances surrounding your firing that you believe was illegal \u2014 whether due to discrimination, retaliation, or violation of public policy.",
    specific_fields: [
      field({
        name: "stated_reason",
        label: "Stated Reason for Termination",
        field_type: "textarea",
        required: true,
        placeholder: "What reason did your employer give for firing you?",
      }),
      field({
        name: "actual_reason",
        label: "Believed Actual Reason",
        field_type: "textarea",
        placeholder:
          "What do you believe is the real reason you were fired?",
      }),
      field({
        name: "tenure_length",
        label: "Length of Employment",
        field_type: "text",
        placeholder: "e.g., 3 years, 6 months",
      }),
      field({
        name: "received_warnings",
        label: "Received Warnings",
        field_type: "boolean",
        help_text:
          "Did you receive any written warnings or performance improvement plans before termination?",
      }),
    ],
    prompts: [
      "What reason did your employer give for firing you? Do you believe this is the real reason?",
      "Were there any recent events (complaints, protected activity, leave requests) that preceded the termination?",
      "Were other employees who did similar things treated differently?",
      "Did you have positive performance reviews before the termination?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Termination letter or written notice",
        "If you were terminated verbally, send an email confirming the conversation to create a written record."
      ),
      evidence(
        "critical",
        "Performance reviews, especially positive ones before termination",
        "A history of good reviews undermines a claim that you were fired for performance reasons."
      ),
      evidence(
        "recommended",
        "Any written warnings or performance improvement plans"
      ),
      evidence(
        "recommended",
        "Communications around the time of termination (emails, texts)",
        "Save any messages that show the timeline of events."
      ),
      evidence(
        "recommended",
        "Evidence of protected activity before termination (complaints, leave requests)"
      ),
      evidence(
        "optional",
        "Final paycheck and documentation of benefits owed"
      ),
    ],
    related_claim_types: ["wrongful_termination"],
    legal_tips: [
      "California is an at-will employment state, but firing someone for an illegal reason (discrimination, retaliation, public policy violation) is wrongful termination.",
      "The timing between a protected activity (filing a complaint, taking leave) and termination can be strong evidence of pretext.",
    ],
  },

  // ── 4. Unpaid Wages ────────────────────────────────────────────────
  unpaid_wages: {
    label: "Unpaid Wages",
    description:
      "Document instances where you were not paid for work performed, including overtime, commissions, or other earned compensation.",
    specific_fields: [
      field({
        name: "hours_worked",
        label: "Hours Worked",
        field_type: "number",
        required: true,
        placeholder: "Number of hours",
      }),
      field({
        name: "hours_paid",
        label: "Hours Paid",
        field_type: "number",
        placeholder: "Number of hours",
      }),
      field({
        name: "pay_period",
        label: "Pay Period",
        field_type: "text",
        placeholder: "e.g., Jan 1-15, 2026",
      }),
      field({
        name: "wage_type",
        label: "Type of Wages",
        field_type: "select",
        options: [
          "Regular wages",
          "Overtime",
          "Double time",
          "Commissions",
          "Bonuses",
          "Vacation/PTO payout",
          "Other",
        ],
      }),
    ],
    prompts: [
      "How many hours did you work that were not paid? What period does this cover?",
      "Were you asked to work off the clock, before clocking in, or after clocking out?",
      "Do you have your own records of hours worked (notes, personal calendar, GPS data)?",
      "Have you raised this issue with your employer? What was their response?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Pay stubs showing hours paid vs. hours actually worked",
        "California employers must provide itemized pay stubs. Request copies if you don't have them."
      ),
      evidence(
        "critical",
        "Personal records of hours worked (notes, calendar, app, GPS data)",
        "Start tracking your hours independently using a personal app or notebook."
      ),
      evidence(
        "recommended",
        "Time clock records or employer's timekeeping system records",
        "Request a copy of your timekeeping records from your employer."
      ),
      evidence(
        "recommended",
        "Employment agreement or offer letter showing agreed pay rate"
      ),
      evidence(
        "recommended",
        "Communications about work assignments (emails, texts requesting off-clock work)"
      ),
      evidence(
        "optional",
        "Coworker statements about similar pay practices"
      ),
    ],
    related_claim_types: ["wage_theft"],
    legal_tips: [
      "California requires employers to pay all wages earned within specific timeframes. You can file a wage claim with the DLSE even while still employed.",
      "Keep your own independent record of hours worked \u2014 if your employer's records are inaccurate, your personal records can serve as evidence.",
    ],
  },

  // ── 5. Retaliation ─────────────────────────────────────────────────
  retaliation: {
    label: "Retaliation",
    description:
      "Document incidents where your employer took negative action against you for exercising a legal right, such as filing a complaint, reporting a violation, or participating in an investigation.",
    specific_fields: [
      field({
        name: "protected_activity",
        label: "Protected Activity",
        field_type: "textarea",
        required: true,
        placeholder:
          "What did you do that you believe triggered the retaliation?",
      }),
      field({
        name: "adverse_action",
        label: "Adverse Action",
        field_type: "textarea",
        placeholder:
          "e.g., demotion, schedule change, termination, reduced hours",
      }),
      field({
        name: "timeline_gap",
        label: "Time Between Activity and Retaliation",
        field_type: "text",
        placeholder: "e.g., 2 weeks, 3 days",
      }),
    ],
    prompts: [
      "What protected activity did you engage in before the retaliation occurred?",
      "How soon after your protected activity did the adverse action happen?",
      "Did your employer's attitude or behavior toward you change after the protected activity?",
      "Were others who engaged in similar protected activities also retaliated against?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Documentation of the protected activity (complaint, report, etc.)",
        "Always keep copies of any complaints or reports you file."
      ),
      evidence(
        "critical",
        "Timeline showing close proximity between protected activity and adverse action",
        "The shorter the gap, the stronger the inference of retaliation."
      ),
      evidence(
        "recommended",
        "Evidence of change in treatment after protected activity",
        "Compare your treatment before and after the protected activity."
      ),
      evidence(
        "recommended",
        "Written notice of the adverse action (demotion letter, schedule change, etc.)"
      ),
      evidence(
        "recommended",
        "Performance evaluations before and after the protected activity"
      ),
    ],
    related_claim_types: ["retaliation_whistleblower"],
    legal_tips: [
      "California Labor Code section 98.6 protects employees from retaliation for filing wage claims, complaints about working conditions, and other protected activities. The filing deadline is 6 months.",
      "Close timing between your protected activity and the adverse action is often the strongest evidence of retaliation.",
    ],
  },

  // ── 6. Family / Medical Leave ──────────────────────────────────────
  family_medical_leave: {
    label: "Family / Medical Leave Violation",
    description:
      "Document incidents where your employer denied, interfered with, or retaliated against you for requesting or taking family or medical leave.",
    specific_fields: [
      field({
        name: "leave_type",
        label: "Type of Leave",
        field_type: "select",
        required: true,
        options: [
          "CFRA/FMLA family leave",
          "Pregnancy disability leave",
          "Bonding leave (new child)",
          "Caring for ill family member",
          "Own serious health condition",
          "Other",
        ],
      }),
      field({
        name: "leave_requested",
        label: "Leave Requested",
        field_type: "boolean",
      }),
      field({
        name: "leave_denied",
        label: "Leave Denied",
        field_type: "boolean",
      }),
      field({
        name: "adverse_action_on_return",
        label: "Adverse Action on Return",
        field_type: "textarea",
        placeholder:
          "Were you demoted, had your position eliminated, or faced other negative consequences?",
      }),
    ],
    prompts: [
      "What type of leave did you request or take, and when?",
      "Was your leave request denied, delayed, or discouraged? What reason was given?",
      "Were you able to return to the same or equivalent position after leave?",
      "Did your employer make negative comments about your leave or discourage you from taking it?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Leave request documentation (written request, email, HR forms)",
        "Always request leave in writing and keep a copy."
      ),
      evidence(
        "critical",
        "Employer's response to leave request (approval, denial, or silence)",
        "If denied verbally, send a follow-up email confirming what was said."
      ),
      evidence(
        "recommended",
        "Medical certification or documentation supporting the need for leave"
      ),
      evidence(
        "recommended",
        "Evidence of position changes upon return (new title, duties, schedule)"
      ),
      evidence(
        "optional",
        "Company leave policy from employee handbook",
        "Compare your employer's actions to their stated policy."
      ),
    ],
    related_claim_types: ["cfra_family_leave"],
    legal_tips: [
      "Under CFRA, eligible employees can take up to 12 weeks of unpaid, job-protected leave per year. Your employer must restore you to the same or comparable position.",
      "Your employer cannot count protected leave against you in attendance policies, performance reviews, or employment decisions.",
    ],
  },

  // ── 7. Workplace Safety ────────────────────────────────────────────
  workplace_safety: {
    label: "Workplace Safety / Health Hazard",
    description:
      "Document unsafe working conditions, health hazards, or safety violations in your workplace.",
    specific_fields: [
      field({
        name: "hazard_type",
        label: "Type of Hazard",
        field_type: "select",
        required: true,
        options: [
          "Chemical exposure",
          "Fall hazard",
          "Electrical hazard",
          "Fire hazard",
          "Ergonomic hazard",
          "Machine/equipment hazard",
          "Violence/threat",
          "Extreme temperature",
          "Inadequate training",
          "Missing safety equipment",
          "Other",
        ],
      }),
      field({
        name: "injury_occurred",
        label: "Injury Occurred",
        field_type: "boolean",
      }),
      field({
        name: "injury_description",
        label: "Injury Description",
        field_type: "textarea",
        placeholder: "Describe any injuries that resulted",
      }),
      field({
        name: "reported_to_employer",
        label: "Reported to Employer",
        field_type: "boolean",
      }),
    ],
    prompts: [
      "Describe the specific hazard or unsafe condition you observed.",
      "Has anyone been injured or become ill because of this hazard?",
      "Did you report the hazard to your employer? How did they respond?",
      "Is this an ongoing hazard, or was it a one-time occurrence?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Photos or videos of the hazardous condition",
        "Take photos with timestamps if you can do so safely."
      ),
      evidence(
        "critical",
        "Written report to employer about the hazard",
        "Report safety concerns in writing (email) for documentation."
      ),
      evidence(
        "recommended",
        "Medical records if injury occurred",
        "Report workplace injuries to your doctor and note the cause."
      ),
      evidence(
        "recommended",
        "OSHA or Cal/OSHA standards that apply to the hazard"
      ),
      evidence(
        "optional",
        "Names of coworkers exposed to the same hazard"
      ),
    ],
    related_claim_types: [],
    legal_tips: [
      "You can file a Cal/OSHA complaint anonymously. Your employer cannot legally retaliate against you for reporting safety concerns.",
      "If there is an imminent danger, Cal/OSHA is required to respond within 3 days. For other hazards, the response time is typically 14 days.",
    ],
  },

  // ── 8. Misclassification ───────────────────────────────────────────
  misclassification: {
    label: "Worker Misclassification",
    description:
      "Document evidence that you have been misclassified as an independent contractor when you should be an employee, or misclassified in your job duties or overtime eligibility.",
    specific_fields: [
      field({
        name: "classification",
        label: "Current Classification",
        field_type: "select",
        required: true,
        options: [
          "Independent contractor (1099)",
          "Exempt employee (no overtime)",
          "Part-time (should be full-time)",
          "Other",
        ],
      }),
      field({
        name: "control_level",
        label: "Level of Employer Control",
        field_type: "textarea",
        placeholder:
          "Describe how much your employer controls when, where, and how you work",
      }),
      field({
        name: "benefits_denied",
        label: "Benefits Denied",
        field_type: "textarea",
        placeholder:
          "e.g., health insurance, overtime pay, meal breaks, workers' comp",
      }),
    ],
    prompts: [
      "How much control does your employer exercise over when, where, and how you perform your work?",
      "Do you use your own tools/equipment, or does the employer provide them?",
      "Can you work for other clients/companies, or does this employer require exclusivity?",
      "What employee benefits (insurance, overtime, breaks, etc.) have you been denied?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Contract or agreement showing your classification",
        "Keep a copy of any agreement that labels you as an independent contractor."
      ),
      evidence(
        "critical",
        "Evidence of employer control (set schedule, required location, provided equipment)",
        "Under California's ABC test, a worker is presumed to be an employee unless the employer proves otherwise."
      ),
      evidence(
        "recommended",
        "Pay records (1099 forms, invoices, pay stubs)"
      ),
      evidence(
        "recommended",
        "Communications showing employer direction and control",
        "Emails or messages where your employer tells you how to do your job are strong evidence."
      ),
      evidence(
        "optional",
        "List of benefits you've been denied"
      ),
    ],
    related_claim_types: ["misclassification"],
    legal_tips: [
      "California uses the ABC test (AB 5) to determine worker classification. Under this test, a worker is presumed to be an employee unless the employer can prove all three prongs.",
      "Misclassified workers can recover unpaid overtime, meal/rest break premiums, business expense reimbursement, and other benefits they were denied.",
    ],
  },

  // ── 9. Meal / Rest Breaks ──────────────────────────────────────────
  meal_rest_breaks: {
    label: "Meal / Rest Break Violations",
    description:
      "Document instances where your employer failed to provide required meal periods or rest breaks, or pressured you to skip or work through them.",
    specific_fields: [
      field({
        name: "break_type",
        label: "Type of Break",
        field_type: "select",
        required: true,
        options: [
          "Meal break (30 min)",
          "Rest break (10 min)",
          "Both meal and rest breaks",
        ],
      }),
      field({
        name: "breaks_missed_count",
        label: "Number of Breaks Missed",
        field_type: "number",
        placeholder: "Total number",
      }),
      field({
        name: "reason_missed",
        label: "Reason Breaks Were Missed",
        field_type: "textarea",
        placeholder:
          "e.g., told to keep working, understaffed, pressure from supervisor",
      }),
      field({
        name: "break_policy_exists",
        label: "Written Break Policy Exists",
        field_type: "boolean",
        help_text:
          "Does your employer have a written meal/rest break policy?",
      }),
    ],
    prompts: [
      "Were you told to skip breaks, or were working conditions such that taking breaks was impractical?",
      "How many breaks have you missed over what time period?",
      "Were you compensated with premium pay for missed breaks?",
      "Do other employees also miss breaks, or is it primarily affecting you?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Time records showing work through meal periods",
        "If your employer auto-deducts meal breaks from your time, note when you actually worked through them."
      ),
      evidence(
        "critical",
        "Personal log of missed breaks with dates and reasons",
        "Start keeping a daily log of every missed break."
      ),
      evidence(
        "recommended",
        "Company break policy from employee handbook"
      ),
      evidence(
        "recommended",
        "Communications from supervisor directing you to skip breaks or keep working",
        "Save any texts or emails where a supervisor tells you to skip a break."
      ),
      evidence(
        "optional",
        "Pay stubs showing whether premium pay was included",
        "Under California law, you're owed one hour of premium pay for each missed break per day."
      ),
    ],
    related_claim_types: ["wage_theft"],
    legal_tips: [
      "California requires a 30-minute meal break before the 5th hour of work and a 10-minute rest break for every 4 hours worked. Employers who fail to provide these owe one hour of premium pay per missed break per day.",
      "Your employer must relieve you of all duties during meal breaks. If you must remain on call or available, the break may be considered 'on duty' and compensable.",
    ],
  },

  // ── 10. Whistleblower ──────────────────────────────────────────────
  whistleblower: {
    label: "Whistleblower",
    description:
      "Document situations where you reported illegal activity, regulatory violations, or unsafe practices by your employer, and any retaliation you faced as a result.",
    specific_fields: [
      field({
        name: "violation_reported",
        label: "Violation Reported",
        field_type: "textarea",
        required: true,
        placeholder:
          "Describe the violation, illegal activity, or unsafe practice you reported",
      }),
      field({
        name: "reported_to",
        label: "Reported To",
        field_type: "textarea",
        placeholder:
          "e.g., supervisor, HR, government agency, law enforcement",
      }),
      field({
        name: "adverse_action",
        label: "Adverse Action",
        field_type: "textarea",
        placeholder:
          "What negative action was taken against you after reporting?",
      }),
    ],
    prompts: [
      "What specific violation or illegal activity did you observe or discover?",
      "Who did you report it to, and when? What was their response?",
      "What negative consequences have you faced since making the report?",
      "Do you have documentation of the underlying violation you reported?",
    ],
    evidence_checklist: [
      evidence(
        "critical",
        "Written report or complaint about the violation (email, form, letter)",
        "Always report violations in writing and keep copies."
      ),
      evidence(
        "critical",
        "Evidence of the underlying violation (documents, photos, records)",
        "Secure copies of evidence before reporting if possible \u2014 access may be restricted afterward."
      ),
      evidence(
        "recommended",
        "Timeline showing connection between report and retaliation"
      ),
      evidence(
        "recommended",
        "Communications showing employer's reaction to your report",
        "Save all communications related to your report and any subsequent treatment changes."
      ),
      evidence(
        "optional",
        "Government agency filings or responses (if reported externally)"
      ),
    ],
    related_claim_types: ["retaliation_whistleblower"],
    legal_tips: [
      "California Labor Code section 1102.5 protects employees who report violations of law to a government or law enforcement agency, or to a supervisor or employee with authority to investigate.",
      "Whistleblower protections apply even if the violation you reported turns out not to be a violation \u2014 as long as you had a reasonable belief that it was.",
    ],
  },
};

// ── Public API ────────────────────────────────────────────────────────

/**
 * Return incident documentation guidance for the given incident type.
 *
 * @throws Error if `incidentType` is not one of the 10 supported types.
 */
export function getIncidentGuide(incidentType: string): IncidentDocResponse {
  const guide = INCIDENT_GUIDES[incidentType];
  if (!guide) {
    const validTypes = Object.keys(INCIDENT_GUIDES).join(", ");
    throw new Error(
      `Unknown incident type: "${incidentType}". Valid types are: ${validTypes}`
    );
  }

  return {
    incident_type: incidentType,
    incident_type_label: guide.label,
    description: guide.description,
    common_fields: COMMON_FIELDS,
    specific_fields: guide.specific_fields,
    prompts: guide.prompts,
    evidence_checklist: guide.evidence_checklist,
    related_claim_types: guide.related_claim_types,
    legal_tips: guide.legal_tips,
    disclaimer: DISCLAIMER,
  };
}
