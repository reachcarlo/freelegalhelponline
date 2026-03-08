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
