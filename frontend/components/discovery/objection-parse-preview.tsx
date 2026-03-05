"use client";

import { useCallback, useState } from "react";
import { useObjectionDrafter } from "@/lib/objection-context";
import { DISCOVERY_TYPE_LABELS, type ResponseDiscoveryType } from "@/lib/objection-api";

export default function ObjectionParsePreview() {
  const { state, dispatch, selectedCount } = useObjectionDrafter();
  const {
    parsedRequests,
    selectedRequestIds,
    skippedSections,
    extractedMetadata,
    detectedType,
    parseWarnings,
  } = state;

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [showSkipped, setShowSkipped] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [showAddManual, setShowAddManual] = useState(false);
  const [manualText, setManualText] = useState("");

  // ── Edit handlers ──────────────────────────────────────────────
  const startEdit = useCallback(
    (id: string, text: string) => {
      setEditingId(id);
      setEditText(text);
    },
    []
  );

  const saveEdit = useCallback(() => {
    if (editingId && editText.trim()) {
      dispatch({ type: "UPDATE_REQUEST", id: editingId, text: editText.trim() });
    }
    setEditingId(null);
    setEditText("");
  }, [editingId, editText, dispatch]);

  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditText("");
  }, []);

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleAddManual = useCallback(() => {
    if (!manualText.trim()) return;
    const dtype = detectedType || "interrogatories";
    dispatch({ type: "ADD_REQUEST", text: manualText.trim(), discoveryType: dtype });
    setManualText("");
    setShowAddManual(false);
  }, [manualText, detectedType, dispatch]);

  // ── Zero requests state ────────────────────────────────────────
  if (parsedRequests.length === 0) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="rounded-lg border border-warning-border bg-warning-bg px-4 py-4 text-sm text-warning-text">
          <p className="font-medium">No discovery requests found</p>
          <p className="mt-2 text-xs">
            This can happen when: (1) the text uses Judicial Council checkbox
            formatting, (2) the requests use unusual numbering, or (3) the
            pasted text doesn&apos;t contain numbered requests. You can add
            requests manually below or go back and adjust your input.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddManual(true)}
          className="text-sm font-medium text-accent hover:underline"
        >
          + Add request manually
        </button>
        {showAddManual && (
          <ManualAddForm
            value={manualText}
            onChange={setManualText}
            onAdd={handleAddManual}
            onCancel={() => setShowAddManual(false)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-text-primary">
          Review Parsed Requests
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          {parsedRequests.length} request{parsedRequests.length !== 1 ? "s" : ""}{" "}
          found.{" "}
          {detectedType && (
            <span className="font-medium">
              Detected type:{" "}
              {DISCOVERY_TYPE_LABELS[detectedType as ResponseDiscoveryType] ||
                detectedType}
            </span>
          )}{" "}
          Review and adjust before generating objections.
        </p>
      </div>

      {/* Warnings */}
      {parseWarnings.length > 0 && (
        <div className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
          {parseWarnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      {/* Extracted metadata */}
      {(extractedMetadata.case_name ||
        extractedMetadata.propounding_party ||
        extractedMetadata.set_number) && (
        <div className="rounded-lg border border-border bg-surface px-4 py-3 text-sm">
          <p className="text-xs font-medium text-text-tertiary mb-1">
            Extracted Metadata
          </p>
          {extractedMetadata.case_name && (
            <p className="text-text-primary">
              <span className="text-text-tertiary">Case: </span>
              {extractedMetadata.case_name}
            </p>
          )}
          <div className="flex gap-4 mt-1">
            {extractedMetadata.propounding_party && (
              <p className="text-text-primary text-xs">
                <span className="text-text-tertiary">Propounding: </span>
                {extractedMetadata.propounding_party}
              </p>
            )}
            {extractedMetadata.responding_party && (
              <p className="text-text-primary text-xs">
                <span className="text-text-tertiary">Responding: </span>
                {extractedMetadata.responding_party}
              </p>
            )}
            {extractedMetadata.set_number != null && (
              <p className="text-text-primary text-xs">
                <span className="text-text-tertiary">Set: </span>
                {extractedMetadata.set_number}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Bulk controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs">
          <button
            type="button"
            onClick={() => dispatch({ type: "SELECT_ALL_REQUESTS" })}
            className="text-accent hover:underline font-medium"
          >
            Select all
          </button>
          <span className="text-text-tertiary">/</span>
          <button
            type="button"
            onClick={() => dispatch({ type: "DESELECT_ALL_REQUESTS" })}
            className="text-accent hover:underline font-medium"
          >
            Deselect all
          </button>
        </div>
        <span className="text-xs text-text-tertiary">
          {selectedCount} of {parsedRequests.length} selected
        </span>
      </div>

      {/* Request card list */}
      <div className="space-y-2">
        {parsedRequests.map((req, idx) => {
          const isSelected = selectedRequestIds.has(req.id);
          const isEditing = editingId === req.id;
          const isExpanded = expandedIds.has(req.id);
          const isLong = req.request_text.length > 200;
          const truncated =
            isLong && !isExpanded
              ? req.request_text.slice(0, 200) + "…"
              : req.request_text;

          return (
            <div
              key={req.id}
              className={`rounded-lg border p-3 transition-colors ${
                isSelected
                  ? "border-border bg-white dark:bg-surface"
                  : "border-border bg-surface opacity-50"
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() =>
                    dispatch({ type: "TOGGLE_REQUEST", id: req.id })
                  }
                  className="mt-1 h-4 w-4 shrink-0 rounded border-border text-accent focus:ring-accent/40"
                  aria-label={`Select request ${req.request_number}`}
                />

                <div className="min-w-0 flex-1">
                  {/* Header */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-text-primary">
                      No. {req.request_number}
                    </span>
                    <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-text-tertiary">
                      {DISCOVERY_TYPE_LABELS[
                        req.discovery_type as ResponseDiscoveryType
                      ] || req.discovery_type}
                    </span>
                  </div>

                  {/* Body */}
                  {isEditing ? (
                    <div className="space-y-2">
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        className="w-full min-h-[80px] rounded-lg border border-border bg-input-bg px-3 py-2 text-sm focus:border-accent focus:outline-none resize-y"
                        aria-label="Edit request text"
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={saveEdit}
                          className="rounded px-3 py-1 text-xs font-medium bg-accent text-white hover:bg-accent-hover"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="rounded px-3 py-1 text-xs font-medium text-text-secondary hover:bg-surface"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-text-secondary whitespace-pre-wrap">
                      {truncated}
                    </p>
                  )}

                  {/* Actions */}
                  {!isEditing && (
                    <div className="flex items-center gap-3 mt-2">
                      {isLong && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(req.id)}
                          className="text-xs text-accent hover:underline"
                        >
                          {isExpanded ? "Show less" : "Show full"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => startEdit(req.id, req.request_text)}
                        className="text-xs text-accent hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const mid = Math.floor(req.request_text.length / 2);
                          dispatch({
                            type: "SPLIT_REQUEST",
                            id: req.id,
                            splitIndex: mid,
                          });
                        }}
                        className="text-xs text-accent hover:underline"
                      >
                        Split
                      </button>
                      {idx < parsedRequests.length - 1 && (
                        <button
                          type="button"
                          onClick={() =>
                            dispatch({ type: "MERGE_REQUESTS", id: req.id })
                          }
                          className="text-xs text-accent hover:underline"
                        >
                          Merge with next
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() =>
                          dispatch({ type: "REMOVE_REQUEST", id: req.id })
                        }
                        className="text-xs text-error-text hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Skipped sections */}
      {skippedSections.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowSkipped(!showSkipped)}
            className="flex items-center gap-1 text-xs font-medium text-text-tertiary hover:text-text-secondary"
            aria-expanded={showSkipped}
          >
            <span className={`transition-transform ${showSkipped ? "rotate-90" : ""}`}>
              &#9654;
            </span>
            Skipped sections ({skippedSections.length})
          </button>
          {showSkipped && (
            <div className="mt-2 space-y-2">
              {skippedSections.map((sec, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-xs"
                >
                  <p className="font-medium text-text-secondary capitalize">
                    {sec.section_type.replace(/_/g, " ")}
                    {sec.defined_terms.length > 0 && (
                      <span className="ml-2 text-text-tertiary">
                        ({sec.defined_terms.length} defined terms)
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-text-tertiary line-clamp-3 whitespace-pre-wrap">
                    {sec.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add manual request */}
      <div>
        {showAddManual ? (
          <ManualAddForm
            value={manualText}
            onChange={setManualText}
            onAdd={handleAddManual}
            onCancel={() => setShowAddManual(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setShowAddManual(true)}
            className="text-sm font-medium text-accent hover:underline"
          >
            + Add request manually
          </button>
        )}
      </div>
    </div>
  );
}

// ── Manual Add Form ──────────────────────────────────────────────────

function ManualAddForm({
  value,
  onChange,
  onAdd,
  onCancel,
}: {
  value: string;
  onChange: (v: string) => void;
  onAdd: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-lg border border-accent/30 bg-accent-surface p-3 space-y-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Enter the request text…"
        className="w-full min-h-[60px] rounded-lg border border-border bg-input-bg px-3 py-2 text-sm focus:border-accent focus:outline-none resize-y"
        aria-label="Manual request text"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onAdd}
          disabled={!value.trim()}
          className={`rounded px-3 py-1 text-xs font-medium ${
            value.trim()
              ? "bg-accent text-white hover:bg-accent-hover"
              : "bg-accent/30 text-text-tertiary cursor-not-allowed"
          }`}
        >
          Add Request
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded px-3 py-1 text-xs font-medium text-text-secondary hover:bg-surface"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
