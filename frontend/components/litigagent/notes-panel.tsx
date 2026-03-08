"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  NoteInfo,
  createNote,
  deleteNote,
  listNotes,
  updateNote,
} from "@/lib/litigagent-api";

interface NotesPanelProps {
  caseId: string;
  selectedFileId: string | null;
  collapsed: boolean;
  onToggle: () => void;
}

export default function NotesPanel({
  caseId,
  selectedFileId,
  collapsed,
  onToggle,
}: NotesPanelProps) {
  const [notes, setNotes] = useState<NoteInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadNotes = useCallback(async () => {
    try {
      const data = await listNotes(caseId);
      setNotes(data.notes);
    } catch {
      // silently fail on load
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const handleCreate = async () => {
    if (!newContent.trim()) return;
    setCreating(true);
    try {
      const note = await createNote(
        caseId,
        newContent.trim(),
        selectedFileId || undefined
      );
      setNotes((prev) => [note, ...prev]);
      setNewContent("");
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  };

  const handleUpdate = async (noteId: string) => {
    if (!editContent.trim()) return;
    try {
      const updated = await updateNote(caseId, noteId, editContent.trim());
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? updated : n))
      );
      setEditingId(null);
      setEditContent("");
    } catch {
      // ignore
    }
  };

  const handleDelete = async (noteId: string) => {
    if (!confirm("Delete this note?")) return;
    try {
      await deleteNote(caseId, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch {
      // ignore
    }
  };

  // Collapsed strip
  if (collapsed) {
    return (
      <button
        onClick={onToggle}
        className="flex h-full w-10 flex-col items-center justify-center border-l border-border bg-surface transition-colors hover:bg-accent-surface"
        title="Show notes"
      >
        <span
          className="text-xs font-medium text-text-tertiary"
          style={{ writingMode: "vertical-rl" }}
        >
          Notes ({notes.length})
        </span>
      </button>
    );
  }

  const textareaCls =
    "w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none transition-colors resize-none";

  return (
    <div className="flex h-full w-[320px] min-w-[320px] flex-col border-l border-border bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text-primary">
          Notes{" "}
          <span className="font-normal text-text-tertiary">
            ({notes.length})
          </span>
        </h2>
        <button
          onClick={onToggle}
          className="rounded p-1 text-text-tertiary transition-colors hover:bg-accent-surface hover:text-accent"
          title="Collapse notes"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
            />
          </svg>
        </button>
      </div>

      {/* Note list */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading && (
          <p className="text-sm text-text-tertiary">Loading notes...</p>
        )}
        {!loading && notes.length === 0 && (
          <p className="text-sm text-text-tertiary">
            No notes yet. Add notes to annotate your case files.
          </p>
        )}
        <div className="space-y-3">
          {notes.map((note) => (
            <div
              key={note.id}
              className="rounded-lg border border-border bg-background p-3"
            >
              {/* Note metadata */}
              <div className="mb-1.5 flex items-center justify-between text-[10px] text-text-tertiary">
                <span>
                  {note.file_id ? "File note" : "Case note"}
                  {" \u00b7 "}
                  {new Date(note.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => {
                      setEditingId(note.id);
                      setEditContent(note.content);
                    }}
                    className="rounded px-1 py-0.5 text-text-tertiary transition-colors hover:text-accent"
                    title="Edit"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(note.id)}
                    className="rounded px-1 py-0.5 text-text-tertiary transition-colors hover:text-error-text"
                    title="Delete"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Edit mode */}
              {editingId === note.id ? (
                <div>
                  <textarea
                    className={textareaCls}
                    rows={3}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    autoFocus
                  />
                  <div className="mt-1.5 flex gap-1.5">
                    <button
                      onClick={() => handleUpdate(note.id)}
                      className="rounded bg-accent px-2 py-1 text-xs text-white hover:bg-accent-hover"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingId(null);
                        setEditContent("");
                      }}
                      className="rounded border border-border px-2 py-1 text-xs text-text-secondary hover:bg-surface"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                  {note.content}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* New note input */}
      <div className="border-t border-border px-4 py-3">
        <textarea
          ref={inputRef}
          className={textareaCls}
          rows={2}
          placeholder={
            selectedFileId
              ? "Add a note for this file..."
              : "Add a case note..."
          }
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              handleCreate();
            }
          }}
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[10px] text-text-tertiary">
            {selectedFileId ? "Linked to selected file" : "General note"}
          </span>
          <button
            onClick={handleCreate}
            disabled={!newContent.trim() || creating}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {creating ? "Adding..." : "Add Note"}
          </button>
        </div>
      </div>
    </div>
  );
}
