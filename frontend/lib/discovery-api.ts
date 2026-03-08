/**
 * API client for discovery document generation endpoints.
 * Mirrors the backend Pydantic schemas in src/employee_help/api/schemas.py.
 */

// ── Types ────────────────────────────────────────────────────────────

export type PartyRole = "plaintiff" | "defendant";

export type DiscoveryToolType =
  | "frogs_general"
  | "frogs_employment"
  | "srogs"
  | "rfpds"
  | "rfas";

export const TOOL_LABELS: Record<DiscoveryToolType, string> = {
  frogs_general: "Form Interrogatories — General (DISC-001)",
  frogs_employment: "Form Interrogatories — Employment (DISC-002)",
  srogs: "Special Interrogatories",
  rfpds: "Requests for Production of Documents",
  rfas: "Requests for Admission",
};

export const TOOL_SHORT_LABELS: Record<DiscoveryToolType, string> = {
  frogs_general: "DISC-001",
  frogs_employment: "DISC-002",
  srogs: "SROGs",
  rfpds: "RFPDs",
  rfas: "RFAs",
};

export interface PartyInfo {
  name: string;
  is_entity: boolean;
  entity_type: string | null;
}

export interface AttorneyInfo {
  name: string;
  sbn: string;
  address: string;
  city_state_zip: string;
  phone: string;
  email: string;
  firm_name: string | null;
  fax: string | null;
  is_pro_per: boolean;
  attorney_for: string;
}

export interface CaseInfo {
  case_number: string;
  court_county: string;
  party_role: PartyRole;
  plaintiffs: PartyInfo[];
  defendants: PartyInfo[];
  attorney: AttorneyInfo;
  court_name: string;
  court_branch: string | null;
  court_address: string | null;
  court_city_zip: string | null;
  judge_name: string | null;
  department: string | null;
  complaint_filed_date: string | null;
  trial_date: string | null;
  does_included: boolean;
  set_number: number;
}

export interface DiscoveryRequest {
  id: string;
  text: string;
  category: string;
  is_selected: boolean;
  is_custom: boolean;
  order: number;
  notes: string | null;
  rfa_type: string | null;
}

// ── Suggest ──────────────────────────────────────────────────────────

export interface SuggestedSectionInfo {
  section_number: string;
  title: string;
  description: string;
}

export interface SuggestedCategoryInfo {
  category: string;
  label: string;
  request_count: number;
}

export interface SuggestResponse {
  tool_type: string;
  party_role: string;
  suggested_sections: SuggestedSectionInfo[];
  suggested_categories: SuggestedCategoryInfo[];
  total_suggested: number;
}

/**
 * Get discovery suggestions based on claim types and party role.
 */
export async function suggestDiscovery(
  claimTypes: string[],
  partyRole: PartyRole,
  toolType: DiscoveryToolType,
  options?: { has_rfas?: boolean; responding_is_entity?: boolean }
): Promise<SuggestResponse> {
  const response = await fetch("/api/discovery/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      claim_types: claimTypes,
      party_role: partyRole,
      tool_type: toolType,
      has_rfas: options?.has_rfas ?? false,
      responding_is_entity: options?.responding_is_entity ?? false,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

// ── Generate ─────────────────────────────────────────────────────────

export interface GenerateOptions {
  tool_type: DiscoveryToolType;
  case_info: CaseInfo;
  selected_sections?: string[];
  selected_requests?: DiscoveryRequest[];
  adverse_actions?: string[];
  custom_definitions?: Record<string, string>;
  include_definitions?: boolean;
}

/**
 * Generate a discovery document and download it.
 * Returns the Blob and suggested filename.
 */
export async function generateDocument(
  options: GenerateOptions
): Promise<{ blob: Blob; filename: string; generationId: string }> {
  const response = await fetch("/api/discovery/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tool_type: options.tool_type,
      case_info: options.case_info,
      selected_sections: options.selected_sections ?? [],
      selected_requests: options.selected_requests ?? [],
      adverse_actions: options.adverse_actions ?? [],
      custom_definitions: options.custom_definitions ?? null,
      include_definitions: options.include_definitions ?? true,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch?.[1] || `discovery.${options.tool_type.includes("frogs") ? "pdf" : "docx"}`;
  const generationId = response.headers.get("X-Generation-Id") || "";

  return { blob, filename, generationId };
}

/**
 * Trigger browser download for a Blob.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Banks ────────────────────────────────────────────────────────────

export interface BankItemInfo {
  id: string;
  text: string;
  category: string;
  order: number;
  rfa_type: string | null;
  applicable_roles: string[] | null;
  applicable_claims: string[] | null;
}

export interface BankCategoryInfo {
  key: string;
  label: string;
  count: number;
}

export interface BankResponse {
  tool_type: string;
  categories: BankCategoryInfo[];
  items: BankItemInfo[];
  total_items: number;
  limit: number | null;
}

/**
 * Get the request bank for a discovery tool, optionally filtered by party role.
 *
 * When partyRole is provided, the backend filters to role-appropriate items
 * and resolves template variables with default labels.
 */
export async function getRequestBank(
  tool: DiscoveryToolType,
  partyRole?: PartyRole
): Promise<BankResponse> {
  const params = partyRole ? `?party_role=${partyRole}` : "";
  const response = await fetch(`/api/discovery/banks/${tool}${params}`);

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

// ── Variable resolution ──────────────────────────────────────────────

const VARIABLE_PATTERN = /\{([A-Z_]+)\}/g;

/**
 * Resolve {PLACEHOLDER} variables in text using case info.
 *
 * Replaces PROPOUNDING_PARTY, RESPONDING_PARTY, PROPOUNDING_DESIGNATION,
 * RESPONDING_DESIGNATION, EMPLOYEE, EMPLOYER. Unknown variables pass through.
 */
export function resolveVariables(text: string, caseInfo: CaseInfo): string {
  const plaintiffName =
    caseInfo.plaintiffs[0]?.name || "Plaintiff";
  const defendantName =
    caseInfo.defendants[0]?.name || "Defendant";

  const vars: Record<string, string> =
    caseInfo.party_role === "plaintiff"
      ? {
          PROPOUNDING_PARTY: plaintiffName,
          RESPONDING_PARTY: defendantName,
          PROPOUNDING_DESIGNATION: "Plaintiff",
          RESPONDING_DESIGNATION: "Defendant",
          EMPLOYEE: plaintiffName,
          EMPLOYER: defendantName,
        }
      : {
          PROPOUNDING_PARTY: defendantName,
          RESPONDING_PARTY: plaintiffName,
          PROPOUNDING_DESIGNATION: "Defendant",
          RESPONDING_DESIGNATION: "Plaintiff",
          EMPLOYEE: plaintiffName,
          EMPLOYER: defendantName,
        };

  return text.replace(VARIABLE_PATTERN, (match, key) => vars[key] ?? match);
}

/**
 * Check if text contains unresolved {VARIABLE} placeholders.
 */
export function hasUnresolvedVariables(text: string): boolean {
  return VARIABLE_PATTERN.test(text);
}

// ── Definitions ──────────────────────────────────────────────────────

export interface DefinitionInfo {
  term: string;
  definition: string;
}

export interface DefinitionsResponse {
  definitions: DefinitionInfo[];
  production_instructions: string;
}

/**
 * Get standard legal definitions and production instructions.
 */
export async function getDefinitions(): Promise<DefinitionsResponse> {
  const response = await fetch("/api/discovery/definitions");

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

// ── Claim type constants (mirrors backend ClaimType enum) ────────────

export const CLAIM_TYPES: { value: string; label: string; group: string }[] = [
  // FEHA claims
  { value: "feha_discrimination", label: "FEHA Discrimination", group: "FEHA" },
  { value: "feha_harassment", label: "FEHA Harassment", group: "FEHA" },
  { value: "feha_retaliation", label: "FEHA Retaliation", group: "FEHA" },
  { value: "feha_failure_to_prevent", label: "FEHA Failure to Prevent", group: "FEHA" },
  { value: "feha_failure_to_accommodate", label: "FEHA Failure to Accommodate", group: "FEHA" },
  { value: "feha_failure_interactive_process", label: "FEHA Failure to Engage Interactive Process", group: "FEHA" },
  { value: "cfra_fmla", label: "CFRA / FMLA Family Leave", group: "FEHA" },
  // Wrongful termination / contract
  { value: "wrongful_termination_public_policy", label: "Wrongful Termination (Public Policy)", group: "Termination" },
  { value: "breach_implied_contract", label: "Breach of Implied Contract", group: "Termination" },
  { value: "breach_covenant_good_faith", label: "Breach of Covenant of Good Faith", group: "Termination" },
  // Wage & hour
  { value: "wage_theft", label: "Wage Theft / Unpaid Wages", group: "Wage & Hour" },
  { value: "meal_rest_break", label: "Meal and Rest Break Violations", group: "Wage & Hour" },
  { value: "overtime", label: "Overtime Violations", group: "Wage & Hour" },
  { value: "misclassification", label: "Worker Misclassification", group: "Wage & Hour" },
  // Retaliation
  { value: "whistleblower_retaliation", label: "Whistleblower Retaliation (Lab. Code 1102.5)", group: "Retaliation" },
  { value: "labor_code_retaliation", label: "Labor Code Retaliation (Lab. Code 98.6)", group: "Retaliation" },
  // Torts & other
  { value: "defamation", label: "Defamation", group: "Torts" },
  { value: "intentional_infliction_emotional_distress", label: "Intentional Infliction of Emotional Distress", group: "Torts" },
  { value: "negligent_infliction_emotional_distress", label: "Negligent Infliction of Emotional Distress", group: "Torts" },
  { value: "paga", label: "PAGA (Private Attorneys General Act)", group: "Other" },
  { value: "unfair_business_practices", label: "Unfair Business Practices (B&P 17200)", group: "Other" },
];

/** Group claim types by their group label for display. */
export function groupClaimTypes(): { group: string; claims: typeof CLAIM_TYPES }[] {
  const groups: Record<string, typeof CLAIM_TYPES> = {};
  for (const ct of CLAIM_TYPES) {
    if (!groups[ct.group]) groups[ct.group] = [];
    groups[ct.group].push(ct);
  }
  return Object.entries(groups).map(([group, claims]) => ({ group, claims }));
}
