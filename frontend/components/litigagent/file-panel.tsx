"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { CaseFileInfo, uploadFiles, deleteFile } from "@/lib/litigagent-api";

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

// ── Filter / Sort constants ───────────────────────────────────

type FileTypeGroup = "pdf" | "email" | "spreadsheet" | "word" | "image" | "other";
type StatusFilter = "all" | "ready" | "processing" | "error";
type SortKey = "upload_order" | "alphabetical" | "file_size" | "page_count";

const FILE_TYPE_GROUP_LABELS: Record<FileTypeGroup, string> = {
  pdf: "PDF",
  email: "Email",
  spreadsheet: "Spreadsheet",
  word: "Word",
  image: "Image",
  other: "Other",
};

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "All",
  ready: "Ready",
  processing: "Processing",
  error: "Errors",
};

const SORT_LABELS: Record<SortKey, string> = {
  upload_order: "Upload order",
  alphabetical: "Alphabetical",
  file_size: "File size",
  page_count: "Page count",
};

function getFileTypeGroup(fileType: string): FileTypeGroup {
  switch (fileType) {
    case "pdf": return "pdf";
    case "eml": case "msg": return "email";
    case "xlsx": case "csv": return "spreadsheet";
    case "docx": return "word";
    case "image": return "image";
    default: return "other";
  }
}

const ACCEPTED_EXTENSIONS = new Set([
  "pdf", "docx", "xlsx", "csv", "tsv", "eml", "msg", "mbox",
  "txt", "md", "rtf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "pptx",
]);

const ACCEPT_STRING = Array.from(ACCEPTED_EXTENSIONS).map((e) => `.${e}`).join(",");

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

function StatusIndicator({ status, ocrConfidence }: {
  status: string;
  ocrConfidence: number | null;
}) {
  switch (status) {
    case "processing":
      return (
        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" title="Processing" aria-label="Processing" />
      );
    case "ready":
      if (ocrConfidence !== null && ocrConfidence < 0.85) {
        return <span className="text-warning-text" title={`OCR confidence: ${Math.round(ocrConfidence * 100)}%`} aria-label={`Ready with low OCR confidence: ${Math.round(ocrConfidence * 100)}%`}>!</span>;
      }
      return <span className="text-verified-text" title="Ready" aria-label="Ready">&#10003;</span>;
    case "error":
      return <span className="text-error-text" title="Error" aria-label="Error">&#10007;</span>;
    default:
      return <span className="text-text-tertiary" title="Queued" aria-label="Queued">&#8226;</span>;
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Recursively extract files from a DataTransfer (supports folder drops). */
async function getFilesFromDrop(dataTransfer: DataTransfer): Promise<File[]> {
  const files: File[] = [];

  // Try webkitGetAsEntry for folder support
  if (dataTransfer.items && dataTransfer.items.length > 0) {
    type FSEntry = { isFile: boolean; isDirectory: boolean; file: (cb: (f: File) => void) => void; createReader: () => { readEntries: (cb: (entries: FSEntry[]) => void) => void } };

    const entries: FSEntry[] = [];
    for (let i = 0; i < dataTransfer.items.length; i++) {
      const item = dataTransfer.items[i];
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const entry = (item as any).webkitGetAsEntry?.() as FSEntry | null;
      if (entry) entries.push(entry);
    }

    if (entries.length > 0) {
      async function readEntry(entry: FSEntry): Promise<void> {
        if (entry.isFile) {
          const file = await new Promise<File>((resolve) => entry.file(resolve));
          files.push(file);
        } else if (entry.isDirectory) {
          const reader = entry.createReader();
          const subEntries = await new Promise<FSEntry[]>((resolve) => reader.readEntries(resolve));
          for (const sub of subEntries) {
            await readEntry(sub);
          }
        }
      }

      for (const entry of entries) {
        await readEntry(entry);
      }

      if (files.length > 0) return files;
    }
  }

  // Fallback: just use dataTransfer.files
  return Array.from(dataTransfer.files);
}

interface FilePanelProps {
  caseId: string;
  files: CaseFileInfo[];
  selectedFileId: string | null;
  onSelectFile: (fileId: string) => void;
  onFilesAdded: (newFiles: CaseFileInfo[]) => void;
  onFileDeleted: (fileId: string) => void;
  processingCount: number;
}

export default function FilePanel({
  caseId,
  files,
  selectedFileId,
  onSelectFile,
  onFilesAdded,
  onFileDeleted,
  processingCount,
}: FilePanelProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCountRef = useRef(0);

  // Filter / search state
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilters, setTypeFilters] = useState<Set<FileTypeGroup>>(new Set());
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortBy, setSortBy] = useState<SortKey>("upload_order");

  const errorCount = files.filter((f) => f.processing_status === "error").length;

  const hasActiveFilters = searchQuery !== "" || typeFilters.size > 0 || statusFilter !== "all" || sortBy !== "upload_order";

  const toggleTypeFilter = useCallback((group: FileTypeGroup) => {
    setTypeFilters((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setSearchQuery("");
    setTypeFilters(new Set());
    setStatusFilter("all");
    setSortBy("upload_order");
  }, []);

  const filteredFiles = useMemo(() => {
    let result = files;

    // Search by filename
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter((f) => f.original_filename.toLowerCase().includes(q));
    }

    // Filter by type group
    if (typeFilters.size > 0) {
      result = result.filter((f) => typeFilters.has(getFileTypeGroup(f.file_type)));
    }

    // Filter by status
    if (statusFilter !== "all") {
      if (statusFilter === "processing") {
        result = result.filter((f) => f.processing_status === "processing" || f.processing_status === "queued");
      } else {
        result = result.filter((f) => f.processing_status === statusFilter);
      }
    }

    // Sort
    if (sortBy !== "upload_order") {
      result = [...result].sort((a, b) => {
        switch (sortBy) {
          case "alphabetical":
            return a.original_filename.localeCompare(b.original_filename);
          case "file_size":
            return b.file_size_bytes - a.file_size_bytes;
          case "page_count":
            return (b.page_count ?? 0) - (a.page_count ?? 0);
          default:
            return 0;
        }
      });
    }

    return result;
  }, [files, searchQuery, typeFilters, statusFilter, sortBy]);

  const validateFiles = useCallback((fileList: File[]): { valid: File[]; errors: string[] } => {
    const valid: File[] = [];
    const errors: string[] = [];
    for (const f of fileList) {
      const ext = f.name.split(".").pop()?.toLowerCase() || "";
      if (!ACCEPTED_EXTENSIONS.has(ext)) {
        errors.push(`${f.name}: unsupported file type (.${ext})`);
        continue;
      }
      if (f.size > MAX_FILE_SIZE) {
        errors.push(`${f.name}: exceeds 50 MB limit (${formatFileSize(f.size)})`);
        continue;
      }
      if (f.size === 0) {
        errors.push(`${f.name}: empty file`);
        continue;
      }
      valid.push(f);
    }
    return { valid, errors };
  }, []);

  const handleUpload = useCallback(async (fileList: File[]) => {
    const { valid, errors } = validateFiles(fileList);
    if (errors.length > 0) {
      setUploadError(errors.join("; "));
    } else {
      setUploadError(null);
    }
    if (valid.length === 0) return;

    setUploading(true);
    try {
      const result = await uploadFiles(caseId, valid);
      onFilesAdded(result.files);
      setUploadError(null);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [caseId, validateFiles, onFilesAdded]);

  // Drag-and-drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCountRef.current++;
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCountRef.current--;
    if (dragCountRef.current <= 0) {
      dragCountRef.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCountRef.current = 0;
    setIsDragOver(false);

    if (uploading) return;

    const droppedFiles = await getFilesFromDrop(e.dataTransfer);
    if (droppedFiles.length > 0) {
      handleUpload(droppedFiles);
    }
  }, [uploading, handleUpload]);

  // Click-to-browse handler
  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const inputFiles = e.target.files;
    if (inputFiles && inputFiles.length > 0) {
      handleUpload(Array.from(inputFiles));
    }
    // Reset so the same file(s) can be selected again
    e.target.value = "";
  }, [handleUpload]);

  // Delete file handler
  const handleDeleteFile = useCallback(async (e: React.MouseEvent, fileId: string) => {
    e.stopPropagation();
    setDeletingId(fileId);
    try {
      await deleteFile(caseId, fileId);
      onFileDeleted(fileId);
    } catch {
      // Silently fail — file may already be deleted
    } finally {
      setDeletingId(null);
    }
  }, [caseId, onFileDeleted]);

  return (
    <div
      className="relative flex h-full w-[280px] min-w-[280px] flex-col border-r border-border bg-surface"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag-over overlay */}
      {isDragOver && (
        <div className="absolute inset-0 z-20 flex items-center justify-center rounded-lg border-2 border-dashed border-accent bg-accent-surface/60">
          <div className="text-center">
            <svg
              className="mx-auto mb-2 h-8 w-8 text-accent"
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
            <p className="text-sm font-medium text-accent">Drop files here</p>
          </div>
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPT_STRING}
        onChange={handleFileInputChange}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Files</h2>
          {files.length > 0 && (
            <button
              type="button"
              onClick={() => setFiltersOpen((o) => !o)}
              className={`rounded p-1 transition-colors ${
                filtersOpen || hasActiveFilters
                  ? "bg-accent-surface text-accent"
                  : "text-text-tertiary hover:bg-accent-surface/50 hover:text-text-secondary"
              }`}
              title={filtersOpen ? "Hide filters" : "Search & filter"}
              aria-label={filtersOpen ? "Hide filters" : "Search & filter"}
              aria-expanded={filtersOpen}
              data-testid="filter-toggle"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </button>
          )}
        </div>
        <p className="mt-0.5 text-xs text-text-tertiary">
          {hasActiveFilters ? (
            <>
              {filteredFiles.length} of {files.length} {files.length === 1 ? "file" : "files"}
            </>
          ) : (
            <>
              {files.length} {files.length === 1 ? "file" : "files"}
            </>
          )}
          {processingCount > 0 && (
            <span className="text-accent"> ({processingCount} processing)</span>
          )}
          {errorCount > 0 && (
            <span className="text-error-text"> ({errorCount} error{errorCount !== 1 ? "s" : ""})</span>
          )}
        </p>
      </div>

      {/* Collapsible filter panel */}
      {filtersOpen && (
        <div className="border-b border-border px-3 py-2 space-y-2" data-testid="filter-panel">
          {/* Search input */}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search files..."
            className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-text-primary placeholder:text-text-tertiary focus:border-accent/50 focus:outline-none"
            data-testid="file-search-input"
          />

          {/* File type filters */}
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Type</p>
            <div className="flex flex-wrap gap-1">
              {(Object.keys(FILE_TYPE_GROUP_LABELS) as FileTypeGroup[]).map((group) => (
                <button
                  key={group}
                  type="button"
                  onClick={() => toggleTypeFilter(group)}
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                    typeFilters.has(group)
                      ? "bg-accent text-white"
                      : "bg-badge-bg text-badge-text hover:bg-accent-surface"
                  }`}
                  data-testid={`type-filter-${group}`}
                >
                  {FILE_TYPE_GROUP_LABELS[group]}
                </button>
              ))}
            </div>
          </div>

          {/* Status filter */}
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Status</p>
            <div className="flex flex-wrap gap-1">
              {(Object.keys(STATUS_LABELS) as StatusFilter[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatusFilter(s)}
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                    statusFilter === s
                      ? "bg-accent text-white"
                      : "bg-badge-bg text-badge-text hover:bg-accent-surface"
                  }`}
                  data-testid={`status-filter-${s}`}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>

          {/* Sort */}
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">Sort</p>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
              className="w-full rounded border border-border bg-background px-2 py-1 text-xs text-text-primary focus:border-accent/50 focus:outline-none"
              data-testid="sort-select"
            >
              {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
                <option key={key} value={key}>{SORT_LABELS[key]}</option>
              ))}
            </select>
          </div>

          {/* Clear filters */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-[10px] text-accent underline"
              data-testid="clear-filters"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Upload error banner */}
      {uploadError && (
        <div className="border-b border-error-border bg-error-bg px-3 py-2">
          <p className="text-xs text-error-text">{uploadError}</p>
          <button
            onClick={() => setUploadError(null)}
            className="mt-1 text-xs text-error-text underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto" role="listbox" aria-label="Case files">
        {files.length === 0 && !uploading ? (
          <button
            type="button"
            onClick={handleBrowseClick}
            className="flex h-full w-full flex-col items-center justify-center px-6 text-center transition-colors hover:bg-accent-surface/30"
          >
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
              Drop files here or click to browse
            </p>
            <p className="mt-1 text-xs text-text-tertiary">
              PDF, DOCX, TXT, EML, MSG, and more
            </p>
          </button>
        ) : filteredFiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-8 text-center">
            <p className="text-sm text-text-tertiary">No files match filters</p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="mt-2 text-xs text-accent underline"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="py-1">
            {filteredFiles.map((f) => (
              <div
                key={f.id}
                role="option"
                aria-selected={selectedFileId === f.id}
                className={`group flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors ${
                  selectedFileId === f.id
                    ? "bg-accent-surface text-accent"
                    : "text-text-primary hover:bg-accent-surface/50"
                }`}
              >
                <button
                  onClick={() => onSelectFile(f.id)}
                  className="flex min-w-0 flex-1 items-center gap-2"
                >
                  <span className="shrink-0 rounded bg-badge-bg px-1 py-0.5 text-[10px] font-bold text-badge-text">
                    {FILE_ICONS[f.file_type] || "???"}
                  </span>
                  <span className="min-w-0 flex-1 truncate" title={f.original_filename}>
                    {f.original_filename}
                  </span>
                </button>
                <span className="flex shrink-0 items-center gap-1">
                  <StatusIndicator
                    status={f.processing_status}
                    ocrConfidence={f.ocr_confidence}
                  />
                  <button
                    onClick={(e) => handleDeleteFile(e, f.id)}
                    disabled={deletingId === f.id}
                    className="ml-0.5 hidden rounded p-0.5 text-text-tertiary transition-colors hover:bg-error-bg hover:text-error-text group-hover:inline-block"
                    title={`Delete ${f.original_filename}`}
                    aria-label={`Delete ${f.original_filename}`}
                  >
                    {deletingId === f.id ? (
                      <span className="inline-block h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                    ) : (
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer — upload button */}
      <div className="border-t border-border px-4 py-3">
        <button
          type="button"
          onClick={handleBrowseClick}
          disabled={uploading}
          className="flex min-h-[36px] w-full items-center justify-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-accent-surface hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? (
            <>
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              Uploading...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Upload Files
            </>
          )}
        </button>
      </div>
    </div>
  );
}
