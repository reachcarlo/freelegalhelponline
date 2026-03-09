/**
 * LITIGAGENT API client — case CRUD, file management, notes, SSE status.
 */

// ── Types ──────────────────────────────────────────────────────

export interface CaseInfo {
  id: string;
  name: string;
  description: string | null;
  status: string;
  file_count: number;
  created_at: string;
  updated_at: string;
}

export interface CaseFileInfo {
  id: string;
  case_id: string;
  original_filename: string;
  file_type: string;
  mime_type: string;
  file_size_bytes: number;
  upload_order: number;
  processing_status: string; // queued | processing | ready | error
  error_message: string | null;
  ocr_confidence: number | null;
  page_count: number | null;
  metadata: Record<string, unknown> | null;
  text_dirty: boolean;
  created_at: string;
  updated_at: string;
}

export interface CaseFileDetail extends CaseFileInfo {
  extracted_text: string | null;
  edited_text: string | null;
}

export interface NoteInfo {
  id: string;
  case_id: string;
  file_id: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface FileStatusEvent {
  file_id: string;
  status: string;
  ocr_confidence?: number;
  page_count?: number;
  message?: string;
}

// ── Case CRUD ──────────────────────────────────────────────────

export async function createCase(
  name: string,
  description?: string
): Promise<CaseInfo> {
  const res = await fetch("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create case (${res.status})`);
  }
  return res.json();
}

export async function listCases(
  status?: string
): Promise<{ cases: CaseInfo[] }> {
  const params = status ? `?status=${status}` : "";
  const res = await fetch(`/api/cases${params}`);
  if (!res.ok) throw new Error(`Failed to list cases (${res.status})`);
  return res.json();
}

export async function getCase(caseId: string): Promise<CaseInfo> {
  const res = await fetch(`/api/cases/${caseId}`);
  if (!res.ok) throw new Error(`Failed to get case (${res.status})`);
  return res.json();
}

export async function updateCase(
  caseId: string,
  updates: { name?: string; description?: string }
): Promise<CaseInfo> {
  const res = await fetch(`/api/cases/${caseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update case (${res.status})`);
  }
  return res.json();
}

export async function archiveCase(caseId: string): Promise<void> {
  const res = await fetch(`/api/cases/${caseId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to archive case (${res.status})`);
}

// ── File Management ────────────────────────────────────────────

export async function uploadFiles(
  caseId: string,
  files: File[]
): Promise<{ files: CaseFileInfo[] }> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f);
  }
  const res = await fetch(`/api/cases/${caseId}/files`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to upload files (${res.status})`);
  }
  return res.json();
}

export async function listFiles(
  caseId: string
): Promise<CaseFileInfo[]> {
  const res = await fetch(`/api/cases/${caseId}/files`);
  if (!res.ok) throw new Error(`Failed to list files (${res.status})`);
  return res.json();
}

export async function getFile(
  caseId: string,
  fileId: string
): Promise<CaseFileDetail> {
  const res = await fetch(`/api/cases/${caseId}/files/${fileId}`);
  if (!res.ok) throw new Error(`Failed to get file (${res.status})`);
  return res.json();
}

export async function updateFileText(
  caseId: string,
  fileId: string,
  editedText: string
): Promise<CaseFileDetail> {
  const res = await fetch(`/api/cases/${caseId}/files/${fileId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edited_text: editedText }),
  });
  if (!res.ok) throw new Error(`Failed to update file text (${res.status})`);
  return res.json();
}

export async function deleteFile(
  caseId: string,
  fileId: string
): Promise<void> {
  const res = await fetch(`/api/cases/${caseId}/files/${fileId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete file (${res.status})`);
}

export async function reprocessFile(
  caseId: string,
  fileId: string
): Promise<CaseFileInfo> {
  const res = await fetch(
    `/api/cases/${caseId}/files/${fileId}/reprocess`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Failed to reprocess file (${res.status})`);
  return res.json();
}

export function getFileDownloadUrl(
  caseId: string,
  fileId: string
): string {
  return `/api/cases/${caseId}/files/${fileId}/download`;
}

// ── SSE Status Stream ──────────────────────────────────────────

export function connectStatusStream(
  caseId: string,
  onEvent: (event: FileStatusEvent) => void,
  onError?: (error: Event) => void
): EventSource {
  const es = new EventSource(`/api/cases/${caseId}/status-stream`);

  es.addEventListener("file_status", (e) => {
    try {
      const data = JSON.parse(e.data) as FileStatusEvent;
      onEvent(data);
    } catch {
      // ignore parse errors
    }
  });

  if (onError) {
    es.onerror = onError;
  }

  return es;
}

// ── Notes ──────────────────────────────────────────────────────

export async function createNote(
  caseId: string,
  content: string,
  fileId?: string
): Promise<NoteInfo> {
  const res = await fetch(`/api/cases/${caseId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, file_id: fileId || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create note (${res.status})`);
  }
  return res.json();
}

export async function listNotes(
  caseId: string,
  fileId?: string
): Promise<{ notes: NoteInfo[] }> {
  const params = fileId ? `?file_id=${fileId}` : "";
  const res = await fetch(`/api/cases/${caseId}/notes${params}`);
  if (!res.ok) throw new Error(`Failed to list notes (${res.status})`);
  return res.json();
}

export async function updateNote(
  caseId: string,
  noteId: string,
  content: string
): Promise<NoteInfo> {
  const res = await fetch(`/api/cases/${caseId}/notes/${noteId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to update note (${res.status})`);
  return res.json();
}

export async function deleteNote(
  caseId: string,
  noteId: string
): Promise<void> {
  const res = await fetch(`/api/cases/${caseId}/notes/${noteId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete note (${res.status})`);
}

// ── Chat Types ────────────────────────────────────────────────

export interface ChatSourceInfo {
  source_type: "case_file" | "knowledge_base";
  title: string;
  relevance_score: number;
  file_id?: string;
  chunk_id?: string;
  content_category?: string;
  heading_path?: string;
}

export interface ChatDoneMetadata {
  query_id: string;
  session_id: string;
  turn_number: number;
  max_turns: number;
  is_final_turn: boolean;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_estimate: number;
  duration_ms: number;
}

export interface ChatCallbacks {
  onSources: (caseSources: ChatSourceInfo[], kbSources: ChatSourceInfo[]) => void;
  onToken: (text: string) => void;
  onDone: (metadata: ChatDoneMetadata) => void;
  onError: (message: string) => void;
}

export interface ChatTurnItem {
  role: "user" | "assistant";
  content: string;
}

export interface ChatSessionInfo {
  id: string;
  case_id: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface ChatTurnInfo {
  id: string;
  session_id: string;
  turn_number: number;
  role: string;
  content: string;
  sources?: Record<string, unknown> | unknown[] | null;
  created_at: string;
}

// ── Chat API ──────────────────────────────────────────────────

/**
 * Send a chat message and stream the response via SSE.
 * Returns an AbortController so the caller can cancel.
 */
export function chatWithCase(
  caseId: string,
  query: string,
  callbacks: ChatCallbacks,
  options?: {
    session_id?: string;
    conversation_history?: ChatTurnItem[];
  }
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const body: Record<string, unknown> = { query };
      if (options?.session_id) body.session_id = options.session_id;
      if (options?.conversation_history) {
        body.conversation_history = options.conversation_history;
      }

      const response = await fetch(`/api/cases/${caseId}/chat`, {
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

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        let dataLines: string[] = [];

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataLines.push(line.slice(6));
          } else if (line === "" && eventType && dataLines.length > 0) {
            const dataStr = dataLines.join("\n");
            try {
              const data = JSON.parse(dataStr);
              switch (eventType) {
                case "sources":
                  callbacks.onSources(
                    data.case_sources || [],
                    data.kb_sources || []
                  );
                  break;
                case "token":
                  callbacks.onToken(data.text || "");
                  break;
                case "done":
                  callbacks.onDone(data as ChatDoneMetadata);
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

export async function listChatSessions(
  caseId: string
): Promise<ChatSessionInfo[]> {
  const res = await fetch(`/api/cases/${caseId}/chat/sessions`);
  if (!res.ok) throw new Error(`Failed to list chat sessions (${res.status})`);
  const data = await res.json();
  return data.sessions;
}

export async function getChatHistory(
  caseId: string,
  sessionId: string
): Promise<ChatTurnInfo[]> {
  const res = await fetch(`/api/cases/${caseId}/chat/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get chat history (${res.status})`);
  const data = await res.json();
  return data.turns;
}

export async function deleteChatSession(
  caseId: string,
  sessionId: string
): Promise<void> {
  const res = await fetch(`/api/cases/${caseId}/chat/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete chat session (${res.status})`);
}
