"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CaseFileInfo, getFile, updateFileText } from "@/lib/litigagent-api";

type SaveStatus = "idle" | "saving" | "saved" | "error";

interface TextPanelProps {
  caseId: string;
  files: CaseFileInfo[];
  selectedFileId: string | null;
}

/** Debounce delay before auto-saving edited text (ms). */
const DEBOUNCE_MS = 2000;
/** How long the "Saved" indicator stays visible (ms). */
const SAVED_DISPLAY_MS = 3000;

export default function TextPanel({ caseId, files, selectedFileId }: TextPanelProps) {
  // Current text being displayed/edited per file
  const [textCache, setTextCache] = useState<Record<string, string>>({});
  // Last-saved text per file (used to detect unsaved changes)
  const [serverText, setServerText] = useState<Record<string, string>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [errorIds, setErrorIds] = useState<Set<string>>(new Set());
  const [saveStatus, setSaveStatus] = useState<Record<string, SaveStatus>>({});
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Fetch text for "ready" files not yet in cache
  const fetchFileText = useCallback(
    async (fileId: string) => {
      setLoadingIds((prev) => new Set(prev).add(fileId));
      setErrorIds((prev) => {
        const next = new Set(prev);
        next.delete(fileId);
        return next;
      });
      try {
        const detail = await getFile(caseId, fileId);
        const text = detail.edited_text || detail.extracted_text || "";
        setTextCache((prev) => ({ ...prev, [fileId]: text }));
        setServerText((prev) => ({ ...prev, [fileId]: text }));
      } catch {
        setErrorIds((prev) => new Set(prev).add(fileId));
      } finally {
        setLoadingIds((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }
    },
    [caseId]
  );

  // Fetch text when files become "ready" and aren't cached yet
  useEffect(() => {
    for (const f of files) {
      if (
        f.processing_status === "ready" &&
        !(f.id in textCache) &&
        !loadingIds.has(f.id) &&
        !errorIds.has(f.id)
      ) {
        fetchFileText(f.id);
      }
    }
  }, [files, textCache, loadingIds, errorIds, fetchFileText]);

  // Scroll to selected file
  useEffect(() => {
    if (!selectedFileId) return;
    const el = document.getElementById(`file-${selectedFileId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedFileId]);

  // Cleanup debounce timers on unmount
  useEffect(() => {
    const timers = debounceTimers.current;
    return () => {
      for (const timer of Object.values(timers)) {
        clearTimeout(timer);
      }
    };
  }, []);

  // Save edited text to backend
  const saveFileText = useCallback(
    async (fileId: string, text: string) => {
      setSaveStatus((prev) => ({ ...prev, [fileId]: "saving" }));
      try {
        await updateFileText(caseId, fileId, text);
        setServerText((prev) => ({ ...prev, [fileId]: text }));
        setSaveStatus((prev) => ({ ...prev, [fileId]: "saved" }));
        setTimeout(() => {
          setSaveStatus((prev) =>
            prev[fileId] === "saved" ? { ...prev, [fileId]: "idle" } : prev
          );
        }, SAVED_DISPLAY_MS);
      } catch {
        setSaveStatus((prev) => ({ ...prev, [fileId]: "error" }));
      }
    },
    [caseId]
  );

  // Handle text change with debounced save
  const handleTextChange = useCallback(
    (fileId: string, newText: string) => {
      setTextCache((prev) => ({ ...prev, [fileId]: newText }));
      setSaveStatus((prev) => ({ ...prev, [fileId]: "idle" }));

      if (debounceTimers.current[fileId]) {
        clearTimeout(debounceTimers.current[fileId]);
      }

      debounceTimers.current[fileId] = setTimeout(() => {
        saveFileText(fileId, newText);
        delete debounceTimers.current[fileId];
      }, DEBOUNCE_MS);
    },
    [saveFileText]
  );

  // Retry a failed save
  const retrySave = useCallback(
    (fileId: string) => {
      const text = textCache[fileId];
      if (text !== undefined) {
        saveFileText(fileId, text);
      }
    },
    [textCache, saveFileText]
  );

  // Check if a file has unsaved local changes
  const hasUnsavedChanges = useCallback(
    (fileId: string): boolean => {
      return (
        fileId in textCache &&
        fileId in serverText &&
        textCache[fileId] !== serverText[fileId]
      );
    },
    [textCache, serverText]
  );

  if (files.length === 0) {
    return (
      <div className="flex h-full flex-1 flex-col items-center justify-center bg-background px-8 text-center">
        <svg
          className="mb-4 h-12 w-12 text-text-tertiary"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
        <h3 className="text-lg font-medium text-text-primary">
          No files uploaded yet
        </h3>
        <p className="mt-1 max-w-sm text-sm text-text-tertiary">
          Upload PDF, Word, email, or text files to extract and view their
          content here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col bg-background">
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-6 py-4">
        {files.map((f) => (
          <div
            key={f.id}
            id={`file-${f.id}`}
            className="mb-6"
            role="region"
            aria-label={`Content from ${f.original_filename}`}
          >
            {/* File section header — sticky */}
            <div className="sticky top-0 z-10 mb-3 rounded-lg border border-border bg-surface px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-badge-bg px-1.5 py-0.5 text-[10px] font-bold uppercase text-badge-text">
                    {f.file_type}
                  </span>
                  <span className="text-sm font-semibold text-text-primary">
                    {f.original_filename}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-text-tertiary">
                  {f.page_count && <span>{f.page_count} pages</span>}
                  {f.ocr_confidence !== null && (
                    <span
                      className={
                        f.ocr_confidence < 0.85
                          ? "text-warning-text"
                          : "text-text-tertiary"
                      }
                    >
                      OCR {Math.round(f.ocr_confidence * 100)}%
                    </span>
                  )}
                  <SaveIndicator
                    status={saveStatus[f.id] || "idle"}
                    hasUnsavedChanges={hasUnsavedChanges(f.id)}
                    onRetry={() => retrySave(f.id)}
                  />
                  <StatusBadge status={f.processing_status} />
                </div>
              </div>
            </div>

            {/* Content area */}
            <FileContent
              file={f}
              text={textCache[f.id]}
              isLoading={loadingIds.has(f.id)}
              hasError={errorIds.has(f.id)}
              onRetry={() => fetchFileText(f.id)}
              onTextChange={(text) => handleTextChange(f.id, text)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Renders the content area for a single file based on its status. */
function FileContent({
  file,
  text,
  isLoading,
  hasError,
  onRetry,
  onTextChange,
}: {
  file: CaseFileInfo;
  text: string | undefined;
  isLoading: boolean;
  hasError: boolean;
  onRetry: () => void;
  onTextChange: (text: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = file.processing_status;

  // Auto-resize textarea when text changes or first loads
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";
    }
  }, [text]);

  if (status === "processing") {
    return (
      <div className="flex items-center gap-2 px-4 py-8 text-sm text-text-tertiary">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Extracting text...
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="rounded-lg border border-error-border bg-error-bg px-4 py-3 text-sm text-error-text">
        {file.error_message || "Failed to extract text from this file."}
      </div>
    );
  }

  if (status === "queued") {
    return (
      <div className="px-4 py-8 text-sm text-text-tertiary">
        Queued for processing...
      </div>
    );
  }

  // status === "ready"
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-4 py-8 text-sm text-text-tertiary">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Loading text...
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="rounded-lg border border-error-border bg-error-bg px-4 py-3 text-sm">
        <span className="text-error-text">Failed to load extracted text. </span>
        <button onClick={onRetry} className="text-accent underline">
          Retry
        </button>
      </div>
    );
  }

  if (text === undefined) {
    // Not fetched yet — will be triggered by useEffect
    return (
      <div className="flex items-center gap-2 px-4 py-8 text-sm text-text-tertiary">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Loading text...
      </div>
    );
  }

  if (text.length === 0) {
    return (
      <div className="px-4 py-6 text-sm italic text-text-tertiary">
        No text content extracted from this file.
      </div>
    );
  }

  return (
    <textarea
      ref={textareaRef}
      value={text}
      onChange={(e) => {
        onTextChange(e.target.value);
        // Immediate height adjustment on input
        e.target.style.height = "auto";
        e.target.style.height = e.target.scrollHeight + "px";
      }}
      className="w-full resize-none rounded-lg border border-transparent bg-transparent px-4 py-2 text-sm leading-relaxed text-text-secondary font-mono focus:border-accent/30 focus:outline-none"
      spellCheck={false}
      aria-label="Editable extracted text"
      data-testid={`editable-text-${file.id}`}
    />
  );
}

/** Shows save status in the file section header. */
function SaveIndicator({
  status,
  hasUnsavedChanges,
  onRetry,
}: {
  status: SaveStatus;
  hasUnsavedChanges: boolean;
  onRetry: () => void;
}) {
  if (status === "saving") {
    return (
      <span className="flex items-center gap-1 text-accent" aria-label="Saving" data-testid="save-status-saving">
        <span className="inline-block h-3 w-3 animate-spin rounded-full border border-accent border-t-transparent" />
        Saving...
      </span>
    );
  }

  if (status === "saved") {
    return (
      <span className="flex items-center gap-1 text-verified-text" aria-label="Saved" data-testid="save-status-saved">
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        Saved
      </span>
    );
  }

  if (status === "error") {
    return (
      <span className="flex items-center gap-1 text-error-text" aria-label="Save failed" data-testid="save-status-error">
        Save failed
        <button onClick={onRetry} className="underline hover:no-underline">
          Retry
        </button>
      </span>
    );
  }

  if (hasUnsavedChanges) {
    return (
      <span className="text-text-tertiary" aria-label="Unsaved changes" data-testid="save-status-unsaved">
        Editing...
      </span>
    );
  }

  return null;
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "ready":
      return (
        <span className="rounded-full bg-verified-bg px-2 py-0.5 text-[10px] font-medium text-verified-text">
          Ready
        </span>
      );
    case "processing":
      return (
        <span className="rounded-full bg-accent-surface px-2 py-0.5 text-[10px] font-medium text-accent">
          Processing
        </span>
      );
    case "error":
      return (
        <span className="rounded-full bg-error-bg px-2 py-0.5 text-[10px] font-medium text-error-text">
          Error
        </span>
      );
    default:
      return (
        <span className="rounded-full bg-badge-bg px-2 py-0.5 text-[10px] font-medium text-badge-text">
          Queued
        </span>
      );
  }
}
