"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CaseFileInfo,
  CaseInfo,
  FileStatusEvent,
  connectStatusStream,
  getCase,
  listFiles,
} from "@/lib/litigagent-api";
import FilePanel from "./file-panel";
import NotesPanel from "./notes-panel";
import TextPanel from "./text-panel";

interface CaseLayoutProps {
  caseId: string;
}

export default function CaseLayout({ caseId }: CaseLayoutProps) {
  const router = useRouter();
  const [caseInfo, setCaseInfo] = useState<CaseInfo | null>(null);
  const [files, setFiles] = useState<CaseFileInfo[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [notesCollapsed, setNotesCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load case info and files
  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [c, f] = await Promise.all([
        getCase(caseId),
        listFiles(caseId),
      ]);
      setCaseInfo(c);
      setFiles(f);
    } catch (e: any) {
      setError(e.message || "Failed to load case");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // SSE status stream — update file statuses in real-time
  useEffect(() => {
    const handleEvent = (event: FileStatusEvent) => {
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id !== event.file_id) return f;
          return {
            ...f,
            processing_status: event.status,
            ocr_confidence: event.ocr_confidence ?? f.ocr_confidence,
            page_count: event.page_count ?? f.page_count,
            error_message: event.message ?? f.error_message,
          };
        })
      );
    };

    const es = connectStatusStream(caseId, handleEvent, () => {
      // On error, reconnect after a short delay
      setTimeout(() => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = connectStatusStream(
            caseId,
            handleEvent
          );
        }
      }, 3000);
    });
    eventSourceRef.current = es;

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [caseId]);

  // Scroll to file in text panel when selected
  const handleSelectFile = (fileId: string) => {
    setSelectedFileId(fileId);
    const el = document.getElementById(`file-${fileId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const processingCount = files.filter(
    (f) => f.processing_status === "processing"
  ).length;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-background">
        <p className="text-text-tertiary">Loading case...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background px-4">
        <div className="rounded-lg border border-error-border bg-error-bg px-6 py-4 text-center">
          <p className="text-sm text-error-text">{error}</p>
          <button
            onClick={() => router.push("/tools/litigagent")}
            className="mt-3 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface"
          >
            Back to Cases
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/tools/litigagent")}
            className="flex items-center gap-1 rounded px-2 py-1 text-sm text-text-tertiary transition-colors hover:bg-accent-surface hover:text-accent"
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
                d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
              />
            </svg>
            Cases
          </button>
          <span className="text-border">|</span>
          <div>
            <h1 className="text-sm font-semibold text-text-primary">
              {caseInfo?.name}
            </h1>
            <p className="text-xs text-text-tertiary">
              {files.length} {files.length === 1 ? "file" : "files"}
              {processingCount > 0 && ` \u00b7 ${processingCount} processing`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Chat button — placeholder for future phases */}
          <button
            className="flex min-h-[36px] items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-accent-surface hover:text-accent"
            title="Chat with case (coming soon)"
            disabled
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
              />
            </svg>
            Chat
          </button>
        </div>
      </div>

      {/* Three-panel content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Panel 1: Files */}
        <FilePanel
          files={files}
          selectedFileId={selectedFileId}
          onSelectFile={handleSelectFile}
          processingCount={processingCount}
        />

        {/* Panel 2: Extracted text */}
        <TextPanel
          files={files}
          selectedFileId={selectedFileId}
        />

        {/* Panel 3: Notes */}
        <NotesPanel
          caseId={caseId}
          selectedFileId={selectedFileId}
          collapsed={notesCollapsed}
          onToggle={() => setNotesCollapsed((v) => !v)}
        />
      </div>
    </div>
  );
}
