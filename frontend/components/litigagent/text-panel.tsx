"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CaseFileInfo, CaseFileDetail, getFile, updateFileText } from "@/lib/litigagent-api";

type SaveStatus = "idle" | "saving" | "saved" | "error";

interface TextPanelProps {
  caseId: string;
  files: CaseFileInfo[];
  selectedFileId: string | null;
}

interface SearchMatch {
  fileId: string;
  start: number;
  end: number;
}

/** Debounce delay before auto-saving edited text (ms). */
const DEBOUNCE_MS = 2000;
/** How long the "Saved" indicator stays visible (ms). */
const SAVED_DISPLAY_MS = 3000;

export default function TextPanel({ caseId, files, selectedFileId }: TextPanelProps) {
  const [textCache, setTextCache] = useState<Record<string, string>>({});
  const [serverText, setServerText] = useState<Record<string, string>>({});
  const [detailCache, setDetailCache] = useState<Record<string, CaseFileDetail>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [errorIds, setErrorIds] = useState<Set<string>>(new Set());
  const [saveStatus, setSaveStatus] = useState<Record<string, SaveStatus>>({});
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const panelRef = useRef<HTMLDivElement>(null);

  // ── Search state ─────────────────────────────────────────────
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Compute all search matches across loaded files (ordered by file upload order)
  const searchMatches = useMemo(() => {
    if (!searchQuery) return [];
    const matches: SearchMatch[] = [];
    const q = searchQuery.toLowerCase();
    for (const f of files) {
      const text = textCache[f.id];
      if (!text) continue;
      const lower = text.toLowerCase();
      let idx = 0;
      while ((idx = lower.indexOf(q, idx)) !== -1) {
        matches.push({ fileId: f.id, start: idx, end: idx + q.length });
        idx += 1;
      }
    }
    return matches;
  }, [files, textCache, searchQuery]);

  // Clamp currentMatchIndex when match count changes
  useEffect(() => {
    if (searchMatches.length === 0) {
      setCurrentMatchIndex(0);
    } else if (currentMatchIndex >= searchMatches.length) {
      setCurrentMatchIndex(searchMatches.length - 1);
    }
  }, [searchMatches.length, currentMatchIndex]);

  // Scroll to the file section containing the current match
  useEffect(() => {
    if (searchMatches.length === 0 || !searchQuery) return;
    const match = searchMatches[currentMatchIndex];
    if (!match) return;
    const el = document.getElementById(`file-${match.fileId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentMatchIndex, searchMatches, searchQuery]);

  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    setSearchQuery("");
    setCurrentMatchIndex(0);
  }, []);

  // Ctrl+F / Cmd+F intercept (capture phase to beat textarea), Escape to close
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "f") {
        e.preventDefault();
        e.stopPropagation();
        setSearchOpen(true);
        requestAnimationFrame(() => {
          searchInputRef.current?.focus();
          searchInputRef.current?.select();
        });
      }
      if (e.key === "Escape" && searchOpen) {
        e.preventDefault();
        closeSearch();
      }
    };
    panel.addEventListener("keydown", handler, true);
    return () => panel.removeEventListener("keydown", handler, true);
  }, [searchOpen, closeSearch]);

  const goToNextMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    setCurrentMatchIndex((prev) => (prev + 1) % searchMatches.length);
  }, [searchMatches.length]);

  const goToPrevMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    setCurrentMatchIndex((prev) => (prev - 1 + searchMatches.length) % searchMatches.length);
  }, [searchMatches.length]);

  // ── Data fetching ────────────────────────────────────────────
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
        setDetailCache((prev) => ({ ...prev, [fileId]: detail }));
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

  useEffect(() => {
    if (!selectedFileId) return;
    const el = document.getElementById(`file-${selectedFileId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedFileId]);

  useEffect(() => {
    const timers = debounceTimers.current;
    return () => {
      for (const timer of Object.values(timers)) {
        clearTimeout(timer);
      }
    };
  }, []);

  // ── Save logic ───────────────────────────────────────────────
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

  const retrySave = useCallback(
    (fileId: string) => {
      const text = textCache[fileId];
      if (text !== undefined) {
        saveFileText(fileId, text);
      }
    },
    [textCache, saveFileText]
  );

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

  // ── Render ───────────────────────────────────────────────────
  const activeMatch =
    searchMatches.length > 0 ? searchMatches[currentMatchIndex] ?? null : null;

  return (
    <div ref={panelRef} className="flex h-full flex-1 flex-col bg-background" tabIndex={-1}>
      {files.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
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
      ) : (
        <>
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-6 py-4">
            {files.map((f) => {
              const fileSearchMatches = searchQuery
                ? searchMatches.filter((m) => m.fileId === f.id)
                : [];
              const activeMatchInFile =
                activeMatch?.fileId === f.id ? activeMatch : null;

              return (
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
                    ocrUsed={detailCache[f.id]?.metadata?.ocr_used === true}
                    onRetry={() => fetchFileText(f.id)}
                    onTextChange={(text) => handleTextChange(f.id, text)}
                    searchMatches={fileSearchMatches}
                    activeMatch={activeMatchInFile}
                  />
                </div>
              );
            })}
          </div>

          {searchOpen && (
            <SearchBar
              inputRef={searchInputRef}
              query={searchQuery}
              onQueryChange={(q) => {
                setSearchQuery(q);
                setCurrentMatchIndex(0);
              }}
              matchCount={searchMatches.length}
              currentIndex={currentMatchIndex}
              onPrev={goToPrevMatch}
              onNext={goToNextMatch}
              onClose={closeSearch}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── FileContent ──────────────────────────────────────────────────

function FileContent({
  file,
  text,
  isLoading,
  hasError,
  ocrUsed,
  onRetry,
  onTextChange,
  searchMatches,
  activeMatch,
}: {
  file: CaseFileInfo;
  text: string | undefined;
  isLoading: boolean;
  hasError: boolean;
  ocrUsed: boolean;
  onRetry: () => void;
  onTextChange: (text: string) => void;
  searchMatches: SearchMatch[];
  activeMatch: SearchMatch | null;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = file.processing_status;

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

  const conf = file.ocr_confidence;
  const showOcrBanner = ocrUsed && conf !== null;
  const isLowConfidence = conf !== null && conf < 0.85;
  const isVeryLowConfidence = conf !== null && conf < 0.7;

  const hasHighlights = searchMatches.length > 0;

  // When search highlights are active, make textarea bg transparent so overlay shows through
  const textareaBg = hasHighlights
    ? "bg-transparent"
    : isVeryLowConfidence
      ? "bg-amber-50/30"
      : isLowConfidence
        ? "bg-amber-50/15"
        : "bg-transparent";

  return (
    <div>
      {showOcrBanner && <OcrConfidenceBanner confidence={conf} />}
      <div className="relative">
        {hasHighlights && (
          <HighlightOverlay
            text={text}
            matches={searchMatches}
            activeMatch={activeMatch}
          />
        )}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            onTextChange(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = e.target.scrollHeight + "px";
          }}
          className={`relative z-[1] w-full resize-none rounded-lg border border-transparent ${textareaBg} px-4 py-2 text-sm leading-relaxed text-text-secondary font-mono focus:border-accent/30 focus:outline-none`}
          spellCheck={false}
          aria-label="Editable extracted text"
          data-testid={`editable-text-${file.id}`}
        />
      </div>
    </div>
  );
}

// ── HighlightOverlay ─────────────────────────────────────────────

function HighlightOverlay({
  text,
  matches,
  activeMatch,
}: {
  text: string;
  matches: SearchMatch[];
  activeMatch: SearchMatch | null;
}) {
  const segments: { text: string; type: "normal" | "match" | "active" }[] = [];
  let lastEnd = 0;

  const sorted = [...matches].sort((a, b) => a.start - b.start);

  for (const m of sorted) {
    if (m.start > lastEnd) {
      segments.push({ text: text.slice(lastEnd, m.start), type: "normal" });
    }
    const isActive =
      activeMatch !== null &&
      m.start === activeMatch.start &&
      m.end === activeMatch.end;
    segments.push({
      text: text.slice(m.start, m.end),
      type: isActive ? "active" : "match",
    });
    lastEnd = m.end;
  }
  if (lastEnd < text.length) {
    segments.push({ text: text.slice(lastEnd), type: "normal" });
  }

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words rounded-lg border border-transparent px-4 py-2 text-sm leading-relaxed text-transparent font-mono"
      aria-hidden="true"
    >
      {segments.map((seg, i) => {
        if (seg.type === "active") {
          return (
            <mark
              key={i}
              className="rounded-sm bg-amber-400/70 text-transparent"
              data-testid="search-highlight-active"
            >
              {seg.text}
            </mark>
          );
        }
        if (seg.type === "match") {
          return (
            <mark
              key={i}
              className="rounded-sm bg-amber-200/60 text-transparent"
              data-testid="search-highlight"
            >
              {seg.text}
            </mark>
          );
        }
        return <span key={i}>{seg.text}</span>;
      })}
    </div>
  );
}

// ── SearchBar ────────────────────────────────────────────────────

function SearchBar({
  inputRef,
  query,
  onQueryChange,
  matchCount,
  currentIndex,
  onPrev,
  onNext,
  onClose,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>;
  query: string;
  onQueryChange: (q: string) => void;
  matchCount: number;
  currentIndex: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className="flex items-center gap-2 border-t border-border bg-surface px-4 py-2"
      data-testid="text-search-bar"
    >
      <svg
        className="h-4 w-4 shrink-0 text-text-tertiary"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (e.shiftKey) onPrev();
            else onNext();
          }
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          }
        }}
        placeholder="Search in text..."
        className="min-w-0 flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none"
        data-testid="text-search-input"
      />
      {query && (
        <span
          className="shrink-0 text-xs text-text-tertiary"
          data-testid="text-search-count"
        >
          {matchCount === 0
            ? "No matches"
            : `${currentIndex + 1} of ${matchCount}`}
        </span>
      )}
      <button
        onClick={onPrev}
        disabled={matchCount === 0}
        className="rounded p-1 text-text-secondary hover:bg-hover disabled:opacity-30"
        aria-label="Previous match"
        data-testid="text-search-prev"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      <button
        onClick={onNext}
        disabled={matchCount === 0}
        className="rounded p-1 text-text-secondary hover:bg-hover disabled:opacity-30"
        aria-label="Next match"
        data-testid="text-search-next"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <button
        onClick={onClose}
        className="rounded p-1 text-text-secondary hover:bg-hover"
        aria-label="Close search"
        data-testid="text-search-close"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ── OcrConfidenceBanner ──────────────────────────────────────────

function OcrConfidenceBanner({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const isLow = confidence < 0.85;
  const isVeryLow = confidence < 0.7;

  if (isVeryLow) {
    return (
      <div
        className="mb-2 flex items-start gap-2 rounded-lg border border-amber-300/50 bg-amber-50/40 px-3 py-2 text-xs text-amber-800"
        role="alert"
        data-testid="ocr-confidence-banner"
      >
        <span className="mt-px shrink-0 font-bold text-amber-600" aria-hidden="true">!</span>
        <span>
          This text was extracted via OCR. Confidence: {pct}%. Please verify for accuracy.
        </span>
      </div>
    );
  }

  if (isLow) {
    return (
      <div
        className="mb-2 flex items-start gap-2 rounded-lg border border-amber-200/50 bg-amber-50/25 px-3 py-2 text-xs text-amber-700"
        role="status"
        data-testid="ocr-confidence-banner"
      >
        <span className="mt-px shrink-0 font-bold text-amber-500" aria-hidden="true">!</span>
        <span>
          Extracted via OCR ({pct}% confidence). Some text may need manual review.
        </span>
      </div>
    );
  }

  return (
    <div
      className="mb-2 rounded-lg border border-border/50 bg-surface/50 px-3 py-2 text-xs text-text-tertiary"
      role="status"
      data-testid="ocr-confidence-banner"
    >
      Extracted via OCR ({pct}% confidence)
    </div>
  );
}

// ── SaveIndicator ────────────────────────────────────────────────

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

// ── StatusBadge ──────────────────────────────────────────────────

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
