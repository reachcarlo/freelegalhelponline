"use client";

import { CaseFileInfo } from "@/lib/litigagent-api";

interface TextPanelProps {
  files: CaseFileInfo[];
  selectedFileId: string | null;
}

export default function TextPanel({ files, selectedFileId }: TextPanelProps) {
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

  // Placeholder rendering — L1.11 will implement full text display
  return (
    <div className="flex h-full flex-1 flex-col bg-background">
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {files.map((f) => (
          <div
            key={f.id}
            id={`file-${f.id}`}
            className="mb-6"
            role="region"
            aria-label={`Content from ${f.original_filename}`}
          >
            {/* File section header */}
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
                  <StatusBadge status={f.processing_status} />
                </div>
              </div>
            </div>

            {/* Content placeholder */}
            {f.processing_status === "processing" && (
              <div className="flex items-center gap-2 px-4 py-8 text-sm text-text-tertiary">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                Extracting text...
              </div>
            )}
            {f.processing_status === "error" && (
              <div className="rounded-lg border border-error-border bg-error-bg px-4 py-3 text-sm text-error-text">
                {f.error_message || "Failed to extract text from this file."}
              </div>
            )}
            {f.processing_status === "queued" && (
              <div className="px-4 py-8 text-sm text-text-tertiary">
                Queued for processing...
              </div>
            )}
            {f.processing_status === "ready" && (
              <div className="px-4 py-2 text-sm leading-relaxed text-text-secondary font-mono whitespace-pre-wrap">
                {/* L1.11 will render actual extracted text here */}
                <span className="text-text-tertiary italic">
                  Text extracted. Full display coming in L1.11.
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
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
