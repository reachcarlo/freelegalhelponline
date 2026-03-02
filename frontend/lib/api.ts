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
