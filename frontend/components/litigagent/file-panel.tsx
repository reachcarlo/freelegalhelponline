"use client";

import { CaseFileInfo } from "@/lib/litigagent-api";

const FILE_ICONS: Record<string, string> = {
  pdf: "PDF",
  docx: "DOC",
  txt: "TXT",
  eml: "EML",
  msg: "MSG",
  xlsx: "XLS",
  csv: "CSV",
  image: "IMG",
  pptx: "PPT",
};

function StatusIndicator({ status, ocrConfidence }: {
  status: string;
  ocrConfidence: number | null;
}) {
  switch (status) {
    case "processing":
      return (
        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" title="Processing" />
      );
    case "ready":
      if (ocrConfidence !== null && ocrConfidence < 0.85) {
        return <span className="text-warning-text" title={`OCR confidence: ${Math.round(ocrConfidence * 100)}%`}>!</span>;
      }
      return <span className="text-verified-text" title="Ready">&#10003;</span>;
    case "error":
      return <span className="text-error-text" title="Error">&#10007;</span>;
    default:
      return <span className="text-text-tertiary" title="Queued">&#8226;</span>;
  }
}

interface FilePanelProps {
  files: CaseFileInfo[];
  selectedFileId: string | null;
  onSelectFile: (fileId: string) => void;
  processingCount: number;
}

export default function FilePanel({
  files,
  selectedFileId,
  onSelectFile,
  processingCount,
}: FilePanelProps) {
  const errorCount = files.filter((f) => f.processing_status === "error").length;

  return (
    <div className="flex h-full w-[280px] min-w-[280px] flex-col border-r border-border bg-surface">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text-primary">Files</h2>
        <p className="mt-0.5 text-xs text-text-tertiary">
          {files.length} {files.length === 1 ? "file" : "files"}
          {processingCount > 0 && (
            <span className="text-accent"> ({processingCount} processing)</span>
          )}
          {errorCount > 0 && (
            <span className="text-error-text"> ({errorCount} error{errorCount !== 1 ? "s" : ""})</span>
          )}
        </p>
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto" role="listbox" aria-label="Case files">
        {files.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <svg
              className="mb-3 h-10 w-10 text-text-tertiary"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-sm text-text-tertiary">
              Drop files here or click upload
            </p>
          </div>
        ) : (
          <div className="py-1">
            {files.map((f) => (
              <button
                key={f.id}
                onClick={() => onSelectFile(f.id)}
                role="option"
                aria-selected={selectedFileId === f.id}
                className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors ${
                  selectedFileId === f.id
                    ? "bg-accent-surface text-accent"
                    : "text-text-primary hover:bg-accent-surface/50"
                }`}
              >
                <span className="shrink-0 rounded bg-badge-bg px-1 py-0.5 text-[10px] font-bold text-badge-text">
                  {FILE_ICONS[f.file_type] || "???"}
                </span>
                <span className="min-w-0 flex-1 truncate" title={f.original_filename}>
                  {f.original_filename}
                </span>
                <span className="shrink-0">
                  <StatusIndicator
                    status={f.processing_status}
                    ocrConfidence={f.ocr_confidence}
                  />
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer — upload button placeholder for L1.10 */}
      <div className="border-t border-border px-4 py-3">
        <div className="text-center text-xs text-text-tertiary">
          Drag &amp; drop to upload
        </div>
      </div>
    </div>
  );
}
