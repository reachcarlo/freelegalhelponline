"use client";

import { useCallback, useMemo, useState } from "react";
import type { BankCategoryInfo, BankItemInfo } from "@/lib/discovery-api";

// ── Types ────────────────────────────────────────────────────────────

interface InterrogatoryPickerProps {
  /** All section groups from the bank endpoint */
  categories: BankCategoryInfo[];
  /** All individual items (subsections) from the bank endpoint */
  items: BankItemInfo[];
  /** Currently selected section numbers (e.g. ["1.1", "2.1", "6.3"]) */
  selected: string[];
  /** Suggested section numbers from the suggest endpoint */
  suggested: string[];
  /** Called when a section is toggled */
  onToggle: (sectionId: string) => void;
  /** Called to select all / deselect all */
  onSetAll: (sectionIds: string[]) => void;
}

// ── Component ────────────────────────────────────────────────────────

export default function InterrogatoryPicker({
  categories,
  items,
  selected,
  suggested,
  onToggle,
  onSetAll,
}: InterrogatoryPickerProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  // Group items by category
  const groupedItems = useMemo(() => {
    const map: Record<string, BankItemInfo[]> = {};
    for (const item of items) {
      if (!map[item.category]) map[item.category] = [];
      map[item.category].push(item);
    }
    return map;
  }, [items]);

  const suggestedSet = useMemo(() => new Set(suggested), [suggested]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const allIds = useMemo(() => items.map((i) => i.id), [items]);

  const toggleGroup = useCallback(
    (categoryKey: string) => {
      setCollapsed((prev) => ({ ...prev, [categoryKey]: !prev[categoryKey] }));
    },
    []
  );

  // Check/uncheck all items in a group
  const toggleGroupSelection = useCallback(
    (categoryKey: string) => {
      const groupItems = groupedItems[categoryKey] || [];
      const groupIds = groupItems.map((i) => i.id);
      const allSelected = groupIds.every((id) => selectedSet.has(id));

      if (allSelected) {
        // Deselect this group
        onSetAll(selected.filter((id) => !groupIds.includes(id)));
      } else {
        // Select all in this group (merge with existing)
        const merged = new Set(selected);
        for (const id of groupIds) merged.add(id);
        onSetAll(Array.from(merged));
      }
    },
    [groupedItems, selectedSet, selected, onSetAll]
  );

  const selectSuggested = useCallback(() => {
    onSetAll(suggested);
  }, [suggested, onSetAll]);

  const selectAll = useCallback(() => {
    onSetAll(allIds);
  }, [allIds, onSetAll]);

  const selectNone = useCallback(() => {
    onSetAll([]);
  }, [onSetAll]);

  return (
    <div>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          type="button"
          onClick={selectSuggested}
          className="rounded-lg border border-accent bg-accent-surface px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20 transition-colors"
        >
          Select suggested ({suggested.length})
        </button>
        <button
          type="button"
          onClick={selectAll}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-border-hover transition-colors"
        >
          Select all
        </button>
        <button
          type="button"
          onClick={selectNone}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-border-hover transition-colors"
        >
          Clear all
        </button>
        <span className="ml-auto text-xs text-text-tertiary">
          {selected.length} of {items.length} selected
        </span>
      </div>

      {/* Section groups */}
      <div className="space-y-2">
        {categories.map((cat) => {
          const groupItems = groupedItems[cat.key] || [];
          const isCollapsed = collapsed[cat.key] ?? false;
          const groupSelectedCount = groupItems.filter((i) =>
            selectedSet.has(i.id)
          ).length;
          const allGroupSelected =
            groupItems.length > 0 && groupSelectedCount === groupItems.length;
          const someGroupSelected =
            groupSelectedCount > 0 && !allGroupSelected;
          const hasSuggested = groupItems.some((i) => suggestedSet.has(i.id));

          return (
            <div
              key={cat.key}
              className={`rounded-lg border transition-colors ${
                hasSuggested && groupSelectedCount === 0
                  ? "border-accent/30"
                  : "border-border"
              }`}
            >
              {/* Group header */}
              <button
                type="button"
                onClick={() => toggleGroup(cat.key)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left"
                aria-expanded={!isCollapsed}
              >
                {/* Group checkbox */}
                <span
                  role="checkbox"
                  aria-label={`Select all in ${cat.label}`}
                  aria-checked={
                    allGroupSelected
                      ? "true"
                      : someGroupSelected
                        ? "mixed"
                        : "false"
                  }
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleGroupSelection(cat.key);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      e.stopPropagation();
                      toggleGroupSelection(cat.key);
                    }
                  }}
                  tabIndex={0}
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                    allGroupSelected
                      ? "border-accent bg-accent text-white"
                      : someGroupSelected
                        ? "border-accent bg-accent/30 text-accent"
                        : "border-border"
                  }`}
                >
                  {allGroupSelected && (
                    <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2.5 6L5 8.5L9.5 4"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                  {someGroupSelected && (
                    <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M3 6H9"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                  )}
                </span>

                {/* Label */}
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-text-primary">
                    {cat.key}. {cat.label}
                  </span>
                  {hasSuggested && (
                    <span className="ml-2 inline-flex items-center rounded-full bg-accent-surface border border-accent/30 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                      suggested
                    </span>
                  )}
                </div>

                {/* Count + chevron */}
                <span className="text-xs text-text-tertiary shrink-0">
                  {groupSelectedCount}/{groupItems.length}
                </span>
                <svg
                  className={`h-4 w-4 text-text-tertiary transition-transform ${
                    isCollapsed ? "" : "rotate-180"
                  }`}
                  viewBox="0 0 16 16"
                  fill="none"
                >
                  <path
                    d="M4 6l4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              {/* Subsections */}
              {!isCollapsed && groupItems.length > 0 && (
                <div className="border-t border-border px-4 py-2 space-y-1">
                  {groupItems.map((item) => {
                    const isSelected = selectedSet.has(item.id);
                    const isSuggested = suggestedSet.has(item.id);

                    return (
                      <label
                        key={item.id}
                        className={`flex items-start gap-3 rounded-md px-2 py-1.5 cursor-pointer transition-colors hover:bg-accent-surface/50 ${
                          !isSuggested && !isSelected
                            ? "opacity-50"
                            : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => onToggle(item.id)}
                          className="mt-0.5 rounded border-border"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm text-text-primary">
                            {item.id}
                          </span>
                          {isSuggested && !isSelected && (
                            <span className="ml-1.5 text-[10px] text-accent">
                              recommended
                            </span>
                          )}
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
