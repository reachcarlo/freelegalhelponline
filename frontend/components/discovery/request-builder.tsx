"use client";

import { useCallback, useMemo, useState } from "react";
import type { DiscoveryRequest, BankCategoryInfo } from "@/lib/discovery-api";

// ── Variable highlighting ─────────────────────────────────────────────

const VAR_RE = /(\{[A-Z_]+\})/g;

/**
 * Render text with any {VARIABLE} placeholders highlighted.
 * Resolved text passes through unchanged.
 */
function HighlightedText({ text }: { text: string }) {
  const parts = text.split(VAR_RE);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((part, i) =>
        VAR_RE.test(part) ? (
          <span
            key={i}
            className="rounded bg-warning-bg px-0.5 text-warning-text"
            title="Unresolved variable — complete case info to resolve"
          >
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

// ── Types ────────────────────────────────────────────────────────────

interface RequestBuilderProps {
  /** All available requests (from bank) */
  requests: DiscoveryRequest[];
  /** Category metadata */
  categories: BankCategoryInfo[];
  /** Suggested category keys from suggest endpoint */
  suggestedCategories: string[];
  /** Update the full request list (toggle, edit, add, reorder) */
  onRequestsChange: (requests: DiscoveryRequest[]) => void;
  /** Numeric limit (35 for SROGs, null for RFPDs) */
  limit: number | null;
  /** For RFAs: only count "fact" type toward limit */
  limitType?: "fact" | null;
  /** Label for the limit (e.g. "interrogatories", "requests") */
  limitLabel?: string;
  /** Tool label for Declaration of Necessity CCP references */
  toolLabel?: string;
}

// ── Limit counter ────────────────────────────────────────────────────

function LimitCounter({
  count,
  limit,
  label,
  toolLabel,
}: {
  count: number;
  limit: number;
  label: string;
  toolLabel?: string;
}) {
  const ratio = count / limit;
  const color =
    ratio >= 1
      ? "text-error-text border-error-border bg-error-bg"
      : ratio >= 0.86 // 30/35
        ? "text-warning-text border-warning-border bg-warning-bg"
        : "text-accent border-accent/30 bg-accent-surface";

  // CCP references differ by tool type
  const ccpRef = toolLabel === "RFAs" ? "CCP \u00A7 2033.050" : "CCP \u00A7 2030.050";

  return (
    <div className={`rounded-lg border px-3 py-2 text-sm font-medium ${color}`}>
      <span className="font-mono">{count}</span>/{limit} {label}
      {count > limit && (
        <div className="mt-1 text-xs font-normal">
          <p className="font-semibold">Declaration of Necessity required</p>
          <p className="mt-0.5">
            Exceeds the {limit}-question limit. You must file a Declaration of
            Necessity per {ccpRef} stating each additional question is warranted
            by the complexity or quantity of existing and potential issues.
          </p>
        </div>
      )}
      {count === limit && (
        <p className="mt-1 text-xs font-normal">At limit.</p>
      )}
      {ratio >= 0.86 && count < limit && (
        <p className="mt-1 text-xs font-normal">
          Approaching limit ({limit - count} remaining).
        </p>
      )}
    </div>
  );
}

// ── Inline editor ────────────────────────────────────────────────────

function RequestRow({
  request,
  index,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  onToggle,
  editText,
  onEditTextChange,
}: {
  request: DiscoveryRequest;
  index: number;
  isEditing: boolean;
  onStartEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onToggle: () => void;
  editText: string;
  onEditTextChange: (text: string) => void;
}) {
  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        request.is_selected
          ? "border-border"
          : "border-border/50 opacity-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={request.is_selected}
          onChange={onToggle}
          aria-label={`Select request ${index + 1}`}
          className="mt-1 rounded border-border shrink-0 focus:ring-2 focus:ring-accent/40"
        />
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => onEditTextChange(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none resize-none"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onSave}
                  disabled={!editText.trim()}
                  className="rounded px-3 py-1 text-xs font-medium text-accent hover:bg-accent-surface transition-colors"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={onCancel}
                  className="rounded px-3 py-1 text-xs font-medium text-text-tertiary hover:text-text-secondary transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={onStartEdit}
              className="text-left w-full group"
            >
              <div className="flex items-start gap-2">
                <span className="text-xs font-mono text-accent shrink-0 mt-0.5">
                  {index + 1}.
                </span>
                <span className="text-sm text-text-secondary group-hover:text-text-primary transition-colors">
                  <HighlightedText text={request.text} />
                </span>
              </div>
              {request.is_custom && (
                <span className="mt-1 inline-flex rounded-full border border-accent/30 bg-accent-surface px-1.5 py-0.5 text-[10px] font-medium text-accent">
                  custom
                </span>
              )}
              {request.rfa_type && (
                <span className="mt-1 ml-1 inline-flex rounded-full border border-border bg-surface px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary">
                  {request.rfa_type}
                </span>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Add custom request ───────────────────────────────────────────────

function AddCustomRequest({
  onAdd,
  rfaMode,
}: {
  onAdd: (text: string, rfaType?: string) => void;
  rfaMode: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [rfaType, setRfaType] = useState("fact");

  const handleAdd = useCallback(() => {
    if (!text.trim()) return;
    onAdd(text.trim(), rfaMode ? rfaType : undefined);
    setText("");
    setOpen(false);
  }, [text, rfaType, rfaMode, onAdd]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full rounded-lg border border-dashed border-border p-3 text-sm text-text-tertiary hover:border-accent hover:text-accent transition-colors"
      >
        + Add Custom Request
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-accent/30 bg-accent-surface/30 p-3 space-y-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter your custom request text…"
        rows={3}
        autoFocus
        className="w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none resize-none"
      />
      {rfaMode && (
        <div className="flex gap-3">
          <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
            <input
              type="radio"
              name="rfa_type"
              value="fact"
              checked={rfaType === "fact"}
              onChange={() => setRfaType("fact")}
            />
            Fact (counts toward 35 limit)
          </label>
          <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
            <input
              type="radio"
              name="rfa_type"
              value="genuineness"
              checked={rfaType === "genuineness"}
              onChange={() => setRfaType("genuineness")}
            />
            Genuineness (unlimited)
          </label>
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleAdd}
          disabled={!text.trim()}
          className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
            text.trim()
              ? "text-accent hover:bg-accent-surface"
              : "text-text-tertiary cursor-not-allowed"
          }`}
        >
          Add Request
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setText("");
          }}
          className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary hover:text-text-secondary transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────

export default function RequestBuilder({
  requests,
  categories,
  suggestedCategories,
  onRequestsChange,
  limit,
  limitType,
  limitLabel = "requests",
  toolLabel,
}: RequestBuilderProps) {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const suggestedSet = useMemo(
    () => new Set(suggestedCategories),
    [suggestedCategories]
  );

  // Count selected toward limit
  const selectedCount = useMemo(() => {
    if (limitType === "fact") {
      return requests.filter(
        (r) => r.is_selected && r.rfa_type === "fact"
      ).length;
    }
    return requests.filter((r) => r.is_selected).length;
  }, [requests, limitType]);

  const totalSelected = useMemo(
    () => requests.filter((r) => r.is_selected).length,
    [requests]
  );

  // Filter requests by active category (or show all selected)
  const visibleRequests = useMemo(() => {
    if (!activeCategory) return requests.filter((r) => r.is_selected);
    return requests.filter((r) => r.category === activeCategory);
  }, [requests, activeCategory]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, { total: number; selected: number }> = {};
    for (const r of requests) {
      if (!counts[r.category]) counts[r.category] = { total: 0, selected: 0 };
      counts[r.category].total++;
      if (r.is_selected) counts[r.category].selected++;
    }
    return counts;
  }, [requests]);

  const handleToggle = useCallback(
    (id: string) => {
      onRequestsChange(
        requests.map((r) =>
          r.id === id ? { ...r, is_selected: !r.is_selected } : r
        )
      );
    },
    [requests, onRequestsChange]
  );

  const handleStartEdit = useCallback(
    (id: string, text: string) => {
      setEditingId(id);
      setEditText(text);
    },
    []
  );

  const handleSaveEdit = useCallback(() => {
    if (!editingId || !editText.trim()) return;
    onRequestsChange(
      requests.map((r) =>
        r.id === editingId ? { ...r, text: editText.trim() } : r
      )
    );
    setEditingId(null);
    setEditText("");
  }, [editingId, editText, requests, onRequestsChange]);

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setEditText("");
  }, []);

  const handleAddCustom = useCallback(
    (text: string, rfaType?: string) => {
      const maxOrder = Math.max(0, ...requests.map((r) => r.order));
      const newReq: DiscoveryRequest = {
        id: `custom_${Date.now()}`,
        text,
        category: activeCategory || "custom",
        is_selected: true,
        is_custom: true,
        order: maxOrder + 1,
        notes: null,
        rfa_type: rfaType || null,
      };
      onRequestsChange([...requests, newReq]);
    },
    [requests, activeCategory, onRequestsChange]
  );

  // Select all / deselect all in active category
  const handleSelectAllCategory = useCallback(
    (cat: string, select: boolean) => {
      onRequestsChange(
        requests.map((r) =>
          r.category === cat ? { ...r, is_selected: select } : r
        )
      );
    },
    [requests, onRequestsChange]
  );

  return (
    <div className="space-y-4">
      {/* Limit counter */}
      {limit !== null && (
        <LimitCounter
          count={selectedCount}
          limit={limit}
          label={limitLabel}
          toolLabel={toolLabel}
        />
      )}

      {/* RFA: show genuineness count separately */}
      {limitType === "fact" && (
        <p className="text-xs text-text-tertiary">
          {totalSelected} total selected ({selectedCount} fact + {totalSelected - selectedCount} genuineness)
        </p>
      )}

      {/* Category cards */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setActiveCategory(null)}
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            activeCategory === null
              ? "border-accent bg-accent-surface text-accent"
              : "border-border text-text-secondary hover:border-border-hover"
          }`}
        >
          Selected ({totalSelected})
        </button>
        {categories.map((cat) => {
          const counts = categoryCounts[cat.key] || { total: 0, selected: 0 };
          const isSuggested = suggestedSet.has(cat.key);
          const isActive = activeCategory === cat.key;

          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveCategory(cat.key)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? "border-accent bg-accent-surface text-accent"
                  : isSuggested
                    ? "border-accent/30 text-text-primary hover:border-accent"
                    : "border-border text-text-secondary hover:border-border-hover"
              }`}
            >
              {cat.label}
              <span className="ml-1 opacity-60">
                {counts.selected}/{counts.total}
              </span>
              {isSuggested && !isActive && (
                <span className="ml-1 text-[10px] text-accent">*</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Category actions */}
      {activeCategory && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleSelectAllCategory(activeCategory, true)}
            className="text-xs text-accent hover:text-accent-hover transition-colors"
          >
            Select all in category
          </button>
          <span className="text-text-tertiary">|</span>
          <button
            type="button"
            onClick={() => handleSelectAllCategory(activeCategory, false)}
            className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
          >
            Deselect all
          </button>
        </div>
      )}

      {/* Request list */}
      <div className="space-y-2">
        {visibleRequests.map((req, i) => (
          <RequestRow
            key={req.id}
            request={req}
            index={i}
            isEditing={editingId === req.id}
            onStartEdit={() => handleStartEdit(req.id, req.text)}
            onSave={handleSaveEdit}
            onCancel={handleCancelEdit}
            onToggle={() => handleToggle(req.id)}
            editText={editText}
            onEditTextChange={setEditText}
          />
        ))}

        {visibleRequests.length === 0 && (
          <p className="py-8 text-center text-sm text-text-tertiary">
            {activeCategory
              ? "No requests in this category."
              : "No requests selected yet. Choose a category above."}
          </p>
        )}
      </div>

      {/* Add custom */}
      <AddCustomRequest
        onAdd={handleAddCustom}
        rfaMode={limitType === "fact"}
      />
    </div>
  );
}
