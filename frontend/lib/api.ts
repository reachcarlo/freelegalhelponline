/**
 * API client for the Employee Help FastAPI backend.
 * Handles SSE streaming from POST /api/ask.
 */

export interface SourceInfo {
  chunk_id: number;
  content_category: string;
  citation: string | null;
  source_url: string;
  heading_path: string;
  relevance_score: number;
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
}

export interface CitationVerification {
  citation_text: string;
  citation_type: "case" | "statute";
  confidence: "verified" | "unverified" | "suspicious";
  verification_status: string;
  detail: string | null;
}

export interface AskMetadata {
  query_id: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_estimate: number;
  duration_ms: number;
  warnings: string[];
  citation_verifications?: CitationVerification[];
  session_id?: string;
  turn_number?: number;
  max_turns?: number;
  is_final_turn?: boolean;
}

export interface AskCallbacks {
  onSources: (sources: SourceInfo[]) => void;
  onToken: (text: string) => void;
  onDone: (metadata: AskMetadata) => void;
  onError: (message: string) => void;
}

export interface AskOptions {
  session_id?: string;
  conversation_history?: ConversationTurn[];
  turn_number?: number;
}

/**
 * Send a question to the API and stream the response via SSE.
 * Returns an AbortController so the caller can cancel the request.
 */
export function askQuestion(
  query: string,
  mode: "consumer" | "attorney",
  callbacks: AskCallbacks,
  options?: AskOptions
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const body: Record<string, unknown> = { query, mode };
      if (options?.session_id) {
        body.session_id = options.session_id;
      }
      if (options?.conversation_history) {
        body.conversation_history = options.conversation_history;
      }
      if (options?.turn_number) {
        body.turn_number = options.turn_number;
      }

      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        const message =
          errorBody?.detail || `Request failed with status ${response.status}`;
        callbacks.onError(message);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        let eventType = "";
        let dataLines: string[] = [];

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataLines.push(line.slice(6));
          } else if (line === "" && eventType && dataLines.length > 0) {
            // Empty line = end of event
            const dataStr = dataLines.join("\n");
            try {
              const data = JSON.parse(dataStr);
              switch (eventType) {
                case "sources":
                  callbacks.onSources(data.sources || []);
                  break;
                case "token":
                  callbacks.onToken(data.text || "");
                  break;
                case "done":
                  callbacks.onDone(data as AskMetadata);
                  break;
                case "error":
                  callbacks.onError(data.message || "Unknown error");
                  break;
              }
            } catch {
              // Skip malformed JSON
            }
            eventType = "";
            dataLines = [];
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      callbacks.onError(
        err instanceof Error ? err.message : "Connection failed"
      );
    }
  })();

  return controller;
}

// ── Deadline calculator ─────────────────────────────────────────────

export interface DeadlineInfo {
  name: string;
  description: string;
  deadline_date: string;
  days_remaining: number;
  urgency: "expired" | "critical" | "urgent" | "normal";
  filing_entity: string;
  portal_url: string;
  legal_citation: string;
  notes: string;
}

export interface DeadlineResponse {
  claim_type: string;
  claim_type_label: string;
  incident_date: string;
  deadlines: DeadlineInfo[];
  disclaimer: string;
}

/**
 * Calculate statute of limitations deadlines.
 */
export async function calculateDeadlines(
  claimType: string,
  incidentDate: string
): Promise<DeadlineResponse> {
  const response = await fetch("/api/deadlines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      claim_type: claimType,
      incident_date: incidentDate,
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

// ── Agency routing guide ─────────────────────────────────────────────

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

/**
 * Get agency routing recommendations for an employment issue.
 */
export async function getAgencyRouting(
  issueType: string,
  isGovernmentEmployee: boolean = false
): Promise<AgencyRoutingResponse> {
  const response = await fetch("/api/agency-routing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      issue_type: issueType,
      is_government_employee: isGovernmentEmployee,
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

// ── Unpaid wages calculator ──────────────────────────────────────────

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

/**
 * Calculate unpaid wages and related damages.
 */
export async function calculateUnpaidWages(
  hourlyRate: number,
  unpaidHours: number,
  employmentStatus: string,
  terminationDate?: string,
  finalWagesPaidDate?: string,
  missedMealBreaks?: number,
  missedRestBreaks?: number,
  unpaidSince?: string
): Promise<UnpaidWagesResponse> {
  const body: Record<string, unknown> = {
    hourly_rate: hourlyRate,
    unpaid_hours: unpaidHours,
    employment_status: employmentStatus,
  };
  if (terminationDate) body.termination_date = terminationDate;
  if (finalWagesPaidDate) body.final_wages_paid_date = finalWagesPaidDate;
  if (missedMealBreaks !== undefined) body.missed_meal_breaks = missedMealBreaks;
  if (missedRestBreaks !== undefined) body.missed_rest_breaks = missedRestBreaks;
  if (unpaidSince) body.unpaid_since = unpaidSince;

  const response = await fetch("/api/unpaid-wages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

// ── Incident documentation helper ────────────────────────────────────

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

/**
 * Get incident documentation guidance for a workplace incident type.
 */
export async function getIncidentGuide(
  incidentType: string
): Promise<IncidentDocResponse> {
  const response = await fetch("/api/incident-guide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident_type: incidentType }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

// ── Guided intake questionnaire ───────────────────────────────────────

export interface IntakeAnswerOptionInfo {
  key: string;
  label: string;
  help_text: string;
}

export interface IntakeQuestionInfo {
  question_id: string;
  question_text: string;
  help_text: string;
  options: IntakeAnswerOptionInfo[];
  allow_multiple: boolean;
  show_if: string[] | null;
}

export interface IntakeQuestionsResponse {
  questions: IntakeQuestionInfo[];
}

export interface ToolRecommendationInfo {
  tool_name: string;
  tool_label: string;
  tool_path: string;
  description: string;
  prefill_params: Record<string, string>;
}

export interface IdentifiedIssueInfo {
  issue_type: string;
  issue_label: string;
  confidence: "high" | "medium";
  description: string;
  related_claim_types: string[];
  tools: ToolRecommendationInfo[];
  has_deadline_urgency: boolean;
}

export interface IntakeResponse {
  identified_issues: IdentifiedIssueInfo[];
  is_government_employee: boolean;
  employment_status: string;
  summary: string;
  disclaimer: string;
}

/**
 * Fetch the guided intake questionnaire.
 */
export async function getIntakeQuestions(): Promise<IntakeQuestionsResponse> {
  const response = await fetch("/api/intake-questions");

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

/**
 * Evaluate intake answers and get identified issues with tool recommendations.
 */
export async function evaluateIntake(
  answers: string[]
): Promise<IntakeResponse> {
  const response = await fetch("/api/intake", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail || `Request failed with status ${response.status}`
    );
  }

  return response.json();
}

/**
 * Submit thumbs up/down feedback for a query.
 * Returns true on success, false on failure.
 */
export async function submitFeedback(
  queryId: string,
  rating: 1 | -1
): Promise<boolean> {
  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_id: queryId, rating }),
    });
    return response.ok;
  } catch {
    return false;
  }
}
