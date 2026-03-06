/**
 * API client for the discovery objection drafter.
 * Mirrors the backend Pydantic schemas in api/objection_routes.py.
 */

// ── Enums / Literals ─────────────────────────────────────────────────

export type ResponseDiscoveryType = "interrogatories" | "rfps" | "rfas";
export type Verbosity = "short" | "medium" | "long";
export type ObjectionStrength = "high" | "medium" | "low";
export type PartyRole = "plaintiff" | "defendant";
export type LitigationPosture = "aggressive" | "balanced" | "selective";
export type ContentScope = "objections_only" | "request_and_objections";

export const DISCOVERY_TYPE_LABELS: Record<ResponseDiscoveryType, string> = {
  interrogatories: "Interrogatories",
  rfps: "Requests for Production",
  rfas: "Requests for Admission",
};

export const VERBOSITY_LABELS: Record<
  Verbosity,
  { label: string; description: string }
> = {
  short: { label: "Short", description: "5–15 words per objection" },
  medium: { label: "Medium", description: "15–30 words per objection" },
  long: { label: "Long", description: "30–60 words (meet-and-confer ready)" },
};

export const POSTURE_LABELS: Record<
  LitigationPosture,
  { label: string; description: string; tooltip: string }
> = {
  aggressive: {
    label: "Aggressive",
    description: "Object broadly to preserve all arguable grounds",
    tooltip:
      "Raises every objection with a colorable basis to preserve the right to assert it later. Courts may overrule some, but waived objections cannot be raised at trial.",
  },
  balanced: {
    label: "Balanced",
    description: "Object where genuinely warranted",
    tooltip:
      "Focuses on objections likely to be sustained. Appropriate when you want to maintain credibility with the court or opposing counsel.",
  },
  selective: {
    label: "Selective",
    description: "Object only to the strongest, most defensible grounds",
    tooltip:
      "Produces a lean response focused on objections a court would almost certainly sustain. Use in cases with a cooperative discovery relationship.",
  },
};

export const STRENGTH_LABELS: Record<
  ObjectionStrength,
  { label: string; color: string; bg: string; border: string }
> = {
  high: {
    label: "High",
    color: "text-verified-text",
    bg: "bg-verified-bg",
    border: "border-verified-border",
  },
  medium: {
    label: "Medium",
    color: "text-warning-text",
    bg: "bg-warning-bg",
    border: "border-warning-border",
  },
  low: {
    label: "Low",
    color: "text-text-tertiary",
    bg: "bg-surface",
    border: "border-border",
  },
};

// ── Grounds ──────────────────────────────────────────────────────────

export interface StatutoryCitationInfo {
  code: string;
  section: string;
  description: string;
}

export interface CaseCitationInfo {
  name: string;
  year: number;
  citation: string;
  reporter_key: string;
  holding?: string;
}

export interface ObjectionGroundInfo {
  ground_id: string;
  label: string;
  category: string;
  description: string;
  applies_to: string[];
  statutory_citations: StatutoryCitationInfo[];
  case_citations: CaseCitationInfo[];
  last_verified: string;
}

export interface GroundsResponse {
  grounds: ObjectionGroundInfo[];
  total: number;
}

export async function getObjectionGrounds(
  discoveryType?: ResponseDiscoveryType
): Promise<GroundsResponse> {
  const params = discoveryType ? `?discovery_type=${discoveryType}` : "";
  const response = await fetch(`/api/objections/grounds${params}`);
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || `Failed to load grounds (${response.status})`);
  }
  return response.json();
}

// ── Parse ────────────────────────────────────────────────────────────

export interface ParsedRequestInfo {
  id: string;
  request_number: number | string;
  request_text: string;
  discovery_type: string;
  is_selected: boolean;
}

export interface SkippedSectionInfo {
  section_type: string;
  content: string;
  defined_terms: string[];
}

export interface ExtractedMetadataInfo {
  propounding_party: string;
  responding_party: string;
  set_number: number | null;
  case_name: string;
}

export interface ParseResponse {
  requests: ParsedRequestInfo[];
  skipped_sections: SkippedSectionInfo[];
  metadata: ExtractedMetadataInfo;
  detected_type: string | null;
  is_response_shell: boolean;
  warnings: string[];
}

export async function parseRequests(
  text: string,
  discoveryType?: ResponseDiscoveryType
): Promise<ParseResponse> {
  const response = await fetch("/api/objections/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      discovery_type: discoveryType ?? null,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || `Parse failed (${response.status})`);
  }
  return response.json();
}

// ── Generate ─────────────────────────────────────────────────────────

export interface ObjectionRequestInput {
  request_number: number;
  request_text: string;
  discovery_type: string;
}

export interface GeneratedObjectionInfo {
  ground_id: string;
  label: string;
  category: string;
  explanation: string;
  strength: ObjectionStrength;
  statutory_citations: StatutoryCitationInfo[];
  case_citations: CaseCitationInfo[];
  citation_warnings: string[];
}

export interface RequestAnalysisInfo {
  request_number: number | string;
  request_text: string;
  discovery_type: string;
  objections: GeneratedObjectionInfo[];
  no_objections_rationale: string | null;
  formatted_output: string;
}

export interface GenerateResponse {
  results: RequestAnalysisInfo[];
  formatted_text: string;
  model_used: string;
  input_tokens: number;
  output_tokens: number;
  cost_estimate: number;
  duration_ms: number;
  warnings: string[];
  disclaimer: string;
}

export interface GenerateOptions {
  requests: ObjectionRequestInput[];
  verbosity: Verbosity;
  party_role: PartyRole;
  posture?: LitigationPosture;
  template?: string;
  separator?: string;
  include_request_text?: boolean;
  include_waiver_language?: boolean;
  ground_ids?: string[];
  model?: string;
}

export async function generateObjections(
  options: GenerateOptions
): Promise<GenerateResponse> {
  const response = await fetch("/api/objections/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(
      err?.detail || `Generation failed (${response.status})`
    );
  }
  return response.json();
}

// ── Document upload ──────────────────────────────────────────────────

export async function parseDocument(
  file: File,
  discoveryType?: ResponseDiscoveryType
): Promise<ParseResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (discoveryType) {
    formData.append("discovery_type", discoveryType);
  }

  const response = await fetch("/api/objections/parse-document", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(
      err?.detail || `Document parse failed (${response.status})`
    );
  }
  return response.json();
}

// ── Export ───────────────────────────────────────────────────────────

export interface ExportDocxOptions {
  results: RequestAnalysisInfo[];
  format: "docx_standalone" | "docx_shell_insert";
  includeRequestText?: boolean;
  includeWaiverLanguage?: boolean;
  enabledObjections?: Record<string, boolean>;
  shellFile?: File;
}

export async function exportDocx(
  options: ExportDocxOptions
): Promise<{ blob: Blob; filename: string }> {
  const formData = new FormData();
  formData.append("results_json", JSON.stringify(options.results));
  formData.append("format", options.format);
  formData.append(
    "include_request_text",
    String(options.includeRequestText ?? false)
  );
  formData.append(
    "include_waiver_language",
    String(options.includeWaiverLanguage ?? false)
  );
  formData.append(
    "enabled_objections_json",
    JSON.stringify(options.enabledObjections ?? {})
  );
  if (options.shellFile) {
    formData.append("shell_file", options.shellFile);
  }

  const response = await fetch("/api/objections/export", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || `Export failed (${response.status})`);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="(.+?)"/);
  const filename = match?.[1] || "objections.docx";

  return { blob, filename };
}

// ── Download helpers ─────────────────────────────────────────────────

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

export function downloadTextFile(text: string, filename: string): void {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  downloadBlob(blob, filename);
}

export function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text);
}
