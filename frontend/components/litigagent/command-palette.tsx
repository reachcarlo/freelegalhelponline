"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

// ── Types ────────────────────────────────────────────────────────

interface PaletteItem {
  key: string;
  label: string;
  segment: string;
  disabled?: boolean;
}

interface CommandPaletteProps {
  caseId: string;
}

// ── Items ────────────────────────────────────────────────────────

const ITEMS: PaletteItem[] = [
  { key: "files", label: "Files", segment: "files" },
  { key: "chat", label: "Chat", segment: "chat" },
  { key: "info", label: "Case Info", segment: "info" },
  { key: "discovery", label: "Discovery", segment: "discovery" },
  { key: "objections", label: "Objections", segment: "objections" },
  { key: "demand", label: "Demand Letter", segment: "demand", disabled: true },
  { key: "timeline", label: "Timeline", segment: "timeline", disabled: true },
  { key: "analysis", label: "Analysis", segment: "analysis", disabled: true },
];

// ── Component ────────────────────────────────────────────────────

export default function CommandPalette({ caseId }: CommandPaletteProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Derive current tool from pathname
  const basePath = `/cases/${caseId}`;
  const currentSegment = pathname.replace(basePath, "").replace(/^\//, "").split("/")[0] || "files";

  // Filter items by query (exclude current tool)
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return ITEMS.filter((item) => {
      if (item.segment === currentSegment) return false;
      if (!q) return true;
      return item.label.toLowerCase().includes(q) || item.key.includes(q);
    });
  }, [query, currentSegment]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }, []);

  const navigate = useCallback(
    (item: PaletteItem) => {
      if (item.disabled) return;
      close();
      router.push(`${basePath}/${item.segment}`);
    },
    [basePath, close, router]
  );

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Keyboard navigation inside palette
  const onInputKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const enabledItems = filtered.filter((i) => !i.disabled);
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[activeIndex];
        if (item && !item.disabled) {
          navigate(item);
        } else if (enabledItems.length === 1) {
          navigate(enabledItems[0]);
        }
      }
    },
    [filtered, activeIndex, close, navigate]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      data-testid="command-palette"
      onClick={close}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />

      {/* Palette */}
      <div
        className="relative w-full max-w-md rounded-xl border border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
      >
        {/* Search input */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
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
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none"
            placeholder="Switch to..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIndex(0); }}
            onKeyDown={onInputKeyDown}
            data-testid="command-palette-input"
          />
          <kbd className="hidden rounded border border-border bg-surface-raised px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary sm:inline-block">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <ul className="max-h-64 overflow-y-auto py-2" role="listbox">
          {filtered.length === 0 && (
            <li className="px-4 py-3 text-center text-sm text-text-tertiary">
              No matching tools
            </li>
          )}
          {filtered.map((item, i) => (
            <li
              key={item.key}
              role="option"
              aria-selected={i === activeIndex}
              aria-disabled={item.disabled || undefined}
              data-testid={`palette-item-${item.key}`}
              className={`flex cursor-pointer items-center justify-between px-4 py-2.5 text-sm transition-colors ${
                item.disabled
                  ? "cursor-default text-text-tertiary/50"
                  : i === activeIndex
                    ? "bg-accent/10 text-accent"
                    : "text-text-primary hover:bg-accent-surface"
              }`}
              onMouseEnter={() => !item.disabled && setActiveIndex(i)}
              onClick={() => navigate(item)}
            >
              <span>{item.label}</span>
              {item.disabled && (
                <span className="text-xs text-text-tertiary/50">Coming soon</span>
              )}
            </li>
          ))}
        </ul>

        {/* Footer hint */}
        <div className="border-t border-border px-4 py-2 text-[11px] text-text-tertiary">
          <span className="mr-3">
            <kbd className="rounded border border-border bg-surface-raised px-1 py-0.5 text-[10px]">↑↓</kbd> navigate
          </span>
          <span className="mr-3">
            <kbd className="rounded border border-border bg-surface-raised px-1 py-0.5 text-[10px]">↵</kbd> select
          </span>
          <span>
            <kbd className="rounded border border-border bg-surface-raised px-1 py-0.5 text-[10px]">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
