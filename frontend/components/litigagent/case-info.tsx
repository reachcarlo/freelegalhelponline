"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CaseContextInfo,
  CaseFactInfo,
  CaseFileInfo,
  addFact,
  confirmFact,
  getCaseContext,
  listFacts,
  supersedeFact,
} from "@/lib/litigagent-api";

interface CaseInfoProps {
  caseId: string;
  files: CaseFileInfo[];
  onClose: () => void;
}

// ── Helpers ───────────────────────────────────────────────────

function sourceLabel(fileId: string | null, files: CaseFileInfo[]): string {
  if (!fileId) return "";
  const f = files.find((x) => x.id === fileId);
  return f ? f.original_filename : fileId;
}

function formatValue(value: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(value)) {
    if (v == null) continue;
    parts.push(`${k}: ${v}`);
  }
  return parts.join(" \u00b7 ");
}

function confidenceBadge(confidence: number): string {
  if (confidence >= 0.9) return "high";
  if (confidence >= 0.7) return "medium";
  return "low";
}

// ── Section components ────────────────────────────────────────

function SectionHeader({
  title,
  count,
  onAdd,
}: {
  title: string;
  count: number;
  onAdd?: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-1.5 pt-3 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
        {title}
      </h3>
      <div className="flex items-center gap-2">
        {count > 0 && (
          <span className="text-xs text-text-tertiary">{count}</span>
        )}
        {onAdd && (
          <button
            onClick={onAdd}
            className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-secondary transition-colors hover:bg-accent-surface hover:text-accent"
            title={`Add ${title.toLowerCase()} fact`}
          >
            + Add
          </button>
        )}
      </div>
    </div>
  );
}

function EmptySection() {
  return (
    <p className="py-2 text-xs italic text-text-tertiary">
      No data extracted yet.
    </p>
  );
}

function FactEditForm({
  fact,
  onSave,
  onCancel,
}: {
  fact: CaseFactInfo;
  onSave: (value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [k, v] of Object.entries(fact.value)) {
      init[k] = v != null ? String(v) : "";
    }
    return init;
  });
  const [effectiveDate, setEffectiveDate] = useState(fact.effective_date ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = () => {
    setSaving(true);
    const value: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(fields)) {
      value[k] = v || null;
    }
    onSave(value, effectiveDate || null);
  };

  return (
    <div className="rounded border border-accent/30 bg-accent/5 px-2 py-2" data-testid="fact-edit-form">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-medium text-text-primary">
          Edit: {fact.fact_type.replace(/_/g, " ")}
        </span>
      </div>
      <div className="space-y-1.5">
        {Object.entries(fields).map(([key, val]) => (
          <div key={key} className="flex items-center gap-2">
            <label className="w-24 shrink-0 text-[10px] font-medium text-text-tertiary">
              {key}
            </label>
            <input
              type="text"
              value={val}
              onChange={(e) =>
                setFields((prev) => ({ ...prev, [key]: e.target.value }))
              }
              className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
              aria-label={`Edit ${key}`}
            />
          </div>
        ))}
        <div className="flex items-center gap-2">
          <label className="w-24 shrink-0 text-[10px] font-medium text-text-tertiary">
            effective date
          </label>
          <input
            type="date"
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
            aria-label="Edit effective date"
          />
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-accent px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="rounded border border-border px-3 py-1 text-xs text-text-secondary transition-colors hover:bg-surface disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// Default field templates for adding new facts per category
const CATEGORY_TEMPLATES: Record<string, { fact_type: string; fields: string[] }[]> = {
  party: [
    { fact_type: "plaintiff", fields: ["name", "role"] },
    { fact_type: "defendant", fields: ["name", "role"] },
  ],
  court: [
    { fact_type: "court", fields: ["court", "county", "department", "judge"] },
  ],
  attorney: [
    { fact_type: "attorney", fields: ["name", "side", "bar_number", "firm", "email"] },
  ],
  employment: [
    { fact_type: "employment_period", fields: ["employer", "position", "department", "compensation_rate", "compensation_type", "pay_period", "start_date", "end_date", "change_reason"] },
  ],
  claim: [
    { fact_type: "claim", fields: ["claim_type", "status", "protected_class", "reason"] },
  ],
  date: [
    { fact_type: "key_date", fields: ["label", "date"] },
  ],
  financial: [
    { fact_type: "financial_event", fields: ["label", "amount", "date"] },
  ],
};

function FactAddForm({
  category,
  onSave,
  onCancel,
}: {
  category: string;
  onSave: (factType: string, value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancel: () => void;
}) {
  const templates = CATEGORY_TEMPLATES[category] || [{ fact_type: category, fields: ["value"] }];
  const [selectedTemplate, setSelectedTemplate] = useState(0);
  const template = templates[selectedTemplate];

  const [fields, setFields] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of template.fields) {
      init[f] = "";
    }
    return init;
  });
  const [effectiveDate, setEffectiveDate] = useState("");
  const [saving, setSaving] = useState(false);

  // Reset fields when template changes
  const handleTemplateChange = (idx: number) => {
    setSelectedTemplate(idx);
    const t = templates[idx];
    const init: Record<string, string> = {};
    for (const f of t.fields) {
      init[f] = "";
    }
    setFields(init);
  };

  const handleSave = () => {
    setSaving(true);
    const value: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(fields)) {
      value[k] = v || null;
    }
    onSave(template.fact_type, value, effectiveDate || null);
  };

  return (
    <div className="rounded border border-green-300/50 bg-green-50/10 px-2 py-2" data-testid="fact-add-form">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-medium text-text-primary">
          Add new fact
        </span>
        {templates.length > 1 && (
          <select
            value={selectedTemplate}
            onChange={(e) => handleTemplateChange(Number(e.target.value))}
            className="rounded border border-border bg-background px-1.5 py-0.5 text-[10px] text-text-primary focus:border-accent focus:outline-none"
            aria-label="Fact type"
          >
            {templates.map((t, i) => (
              <option key={t.fact_type} value={i}>
                {t.fact_type.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="space-y-1.5">
        {Object.entries(fields).map(([key, val]) => (
          <div key={key} className="flex items-center gap-2">
            <label className="w-24 shrink-0 text-[10px] font-medium text-text-tertiary">
              {key}
            </label>
            <input
              type="text"
              value={val}
              onChange={(e) =>
                setFields((prev) => ({ ...prev, [key]: e.target.value }))
              }
              className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
              aria-label={`New ${key}`}
            />
          </div>
        ))}
        <div className="flex items-center gap-2">
          <label className="w-24 shrink-0 text-[10px] font-medium text-text-tertiary">
            effective date
          </label>
          <input
            type="date"
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
            aria-label="New effective date"
          />
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-accent px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
        >
          {saving ? "Adding..." : "Add"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="rounded border border-border px-3 py-1 text-xs text-text-secondary transition-colors hover:bg-surface disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function formatDateRange(start: unknown, end: unknown): string {
  const s = start ? String(start) : null;
  const e = end ? String(end) : null;
  if (s && e) return `${s} → ${e}`;
  if (s) return `${s} → present`;
  if (e) return `until ${e}`;
  return "";
}

function formatCompensation(rate: unknown, type: unknown, period: unknown): string {
  if (!rate) return "";
  const parts: string[] = [];
  const num = Number(rate);
  if (!isNaN(num)) {
    parts.push(`$${num.toLocaleString()}`);
  } else {
    parts.push(String(rate));
  }
  if (type) parts.push(String(type));
  if (period) parts.push(`/ ${period}`);
  return parts.join(" ");
}

function EmploymentRow({
  fact,
  files,
  onConfirm,
  onEdit,
  editingFactId,
  onSaveEdit,
  onCancelEdit,
}: {
  fact: CaseFactInfo;
  files: CaseFileInfo[];
  onConfirm: (factId: string) => void;
  onEdit: (factId: string) => void;
  editingFactId: string | null;
  onSaveEdit: (factId: string, value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancelEdit: () => void;
}) {
  if (editingFactId === fact.id) {
    return (
      <FactEditForm
        fact={fact}
        onSave={(value, effectiveDate) => onSaveEdit(fact.id, value, effectiveDate)}
        onCancel={onCancelEdit}
      />
    );
  }

  const v = fact.value;
  const badge = confidenceBadge(fact.confidence);
  const dateRange = formatDateRange(v.start_date, v.end_date);
  const comp = formatCompensation(v.compensation_rate, v.compensation_type, v.pay_period);
  const employer = v.employer ? String(v.employer) : null;
  const position = v.position ? String(v.position) : null;
  const department = v.department ? String(v.department) : null;
  const changeReason = v.change_reason ? String(v.change_reason) : null;

  return (
    <div className="group rounded border border-border/50 px-3 py-2 hover:bg-surface" data-testid="employment-row">
      {/* Header: employer + position */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">
              {employer || fact.fact_type.replace(/_/g, " ")}
            </span>
            <span
              className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                badge === "high"
                  ? "bg-green-100 text-green-700"
                  : badge === "medium"
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {Math.round(fact.confidence * 100)}%
            </span>
            <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-text-tertiary">
              {fact.extraction_method}
            </span>
          </div>
          {position && (
            <p className="mt-0.5 text-xs text-text-secondary">
              {position}
              {department ? ` · ${department}` : ""}
            </p>
          )}
        </div>
        <div className="mt-0.5 flex shrink-0 items-center gap-1">
          {fact.confirmed ? (
            <span className="text-[10px] font-medium text-green-600" title="Confirmed">
              Confirmed
            </span>
          ) : (
            <button
              onClick={() => onConfirm(fact.id)}
              className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
              title="Confirm this fact"
            >
              Confirm
            </button>
          )}
          <button
            onClick={() => onEdit(fact.id)}
            className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
            title="Edit this fact"
          >
            Edit
          </button>
        </div>
      </div>
      {/* Details row */}
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        {dateRange && (
          <span className="text-[11px] text-text-secondary" data-testid="employment-dates">
            {dateRange}
          </span>
        )}
        {comp && (
          <span className="text-[11px] text-text-secondary" data-testid="employment-compensation">
            {comp}
          </span>
        )}
        {changeReason && (
          <span className="rounded bg-amber-100/60 px-1.5 py-0.5 text-[10px] font-medium text-amber-700" data-testid="employment-reason">
            {changeReason}
          </span>
        )}
      </div>
      {/* Source */}
      {fact.source_file_id && (
        <p className="mt-1 text-[10px] text-text-tertiary">
          Source: {sourceLabel(fact.source_file_id, files)}
        </p>
      )}
    </div>
  );
}

const CLAIM_STATUSES = ["active", "dropped", "amended", "settled"] as const;

const CLAIM_STATUS_STYLES: Record<string, string> = {
  active: "bg-blue-100 text-blue-700 border-blue-200",
  dropped: "bg-gray-100 text-gray-500 border-gray-200",
  amended: "bg-amber-100 text-amber-700 border-amber-200",
  settled: "bg-green-100 text-green-700 border-green-200",
};

function ClaimRow({
  fact,
  files,
  onConfirm,
  onEdit,
  editingFactId,
  onSaveEdit,
  onCancelEdit,
  onStatusChange,
}: {
  fact: CaseFactInfo;
  files: CaseFileInfo[];
  onConfirm: (factId: string) => void;
  onEdit: (factId: string) => void;
  editingFactId: string | null;
  onSaveEdit: (factId: string, value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancelEdit: () => void;
  onStatusChange: (factId: string, newStatus: string) => void;
}) {
  if (editingFactId === fact.id) {
    return (
      <FactEditForm
        fact={fact}
        onSave={(value, effectiveDate) => onSaveEdit(fact.id, value, effectiveDate)}
        onCancel={onCancelEdit}
      />
    );
  }

  const v = fact.value;
  const badge = confidenceBadge(fact.confidence);
  const claimType = v.claim_type ? String(v.claim_type).replace(/_/g, " ") : fact.fact_type.replace(/_/g, " ");
  const status = v.status ? String(v.status).toLowerCase() : "active";
  const protectedClass = v.protected_class ? String(v.protected_class) : null;
  const reason = v.reason ? String(v.reason) : null;
  const statusStyle = CLAIM_STATUS_STYLES[status] || CLAIM_STATUS_STYLES.active;

  return (
    <div className="group rounded border border-border/50 px-3 py-2 hover:bg-surface" data-testid="claim-row">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">
              {claimType}
            </span>
            <span
              className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                badge === "high"
                  ? "bg-green-100 text-green-700"
                  : badge === "medium"
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {Math.round(fact.confidence * 100)}%
            </span>
            <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-text-tertiary">
              {fact.extraction_method}
            </span>
          </div>
          {protectedClass && (
            <p className="mt-0.5 text-xs text-text-secondary">
              Protected class: {protectedClass}
            </p>
          )}
          {reason && (
            <p className="mt-0.5 text-xs text-text-secondary">
              {reason}
            </p>
          )}
          {fact.source_file_id && (
            <p className="mt-0.5 text-[10px] text-text-tertiary">
              Source: {sourceLabel(fact.source_file_id, files)}
            </p>
          )}
        </div>
        <div className="mt-0.5 flex shrink-0 items-center gap-1">
          <select
            value={status}
            onChange={(e) => onStatusChange(fact.id, e.target.value)}
            className={`rounded border px-1.5 py-0.5 text-[10px] font-medium focus:outline-none ${statusStyle}`}
            aria-label="Claim status"
            data-testid="claim-status-select"
          >
            {CLAIM_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
          {fact.confirmed ? (
            <span className="text-[10px] font-medium text-green-600" title="Confirmed">
              Confirmed
            </span>
          ) : (
            <button
              onClick={() => onConfirm(fact.id)}
              className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
              title="Confirm this fact"
            >
              Confirm
            </button>
          )}
          <button
            onClick={() => onEdit(fact.id)}
            className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
            title="Edit this fact"
          >
            Edit
          </button>
        </div>
      </div>
    </div>
  );
}

function formatCurrency(amount: unknown): string {
  if (amount == null) return "";
  const num = Number(amount);
  if (isNaN(num)) return String(amount);
  return `$${num.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function FinancialRow({
  fact,
  files,
  onConfirm,
  onEdit,
  editingFactId,
  onSaveEdit,
  onCancelEdit,
}: {
  fact: CaseFactInfo;
  files: CaseFileInfo[];
  onConfirm: (factId: string) => void;
  onEdit: (factId: string) => void;
  editingFactId: string | null;
  onSaveEdit: (factId: string, value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancelEdit: () => void;
}) {
  if (editingFactId === fact.id) {
    return (
      <FactEditForm
        fact={fact}
        onSave={(value, effectiveDate) => onSaveEdit(fact.id, value, effectiveDate)}
        onCancel={onCancelEdit}
      />
    );
  }

  const v = fact.value;
  const badge = confidenceBadge(fact.confidence);
  const label = v.label ? String(v.label) : fact.fact_type.replace(/_/g, " ");
  const amount = formatCurrency(v.amount);
  const date = v.date ? String(v.date) : fact.effective_date ?? null;

  return (
    <div className="group flex items-center gap-3 rounded px-2 py-1.5 hover:bg-surface" data-testid="financial-row">
      {/* Date column */}
      <div className="w-20 shrink-0 text-[11px] text-text-tertiary" data-testid="financial-date">
        {date || "—"}
      </div>
      {/* Label + amount */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary" data-testid="financial-label">
            {label}
          </span>
          {amount && (
            <span className="text-sm font-semibold text-text-primary" data-testid="financial-amount">
              {amount}
            </span>
          )}
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
              badge === "high"
                ? "bg-green-100 text-green-700"
                : badge === "medium"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {Math.round(fact.confidence * 100)}%
          </span>
          <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-text-tertiary">
            {fact.extraction_method}
          </span>
        </div>
        {fact.source_file_id && (
          <p className="mt-0.5 text-[10px] text-text-tertiary">
            Source: {sourceLabel(fact.source_file_id, files)}
          </p>
        )}
      </div>
      {/* Actions */}
      <div className="flex shrink-0 items-center gap-1">
        {fact.confirmed ? (
          <span className="text-[10px] font-medium text-green-600" title="Confirmed">
            Confirmed
          </span>
        ) : (
          <button
            onClick={() => onConfirm(fact.id)}
            className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
            title="Confirm this fact"
          >
            Confirm
          </button>
        )}
        <button
          onClick={() => onEdit(fact.id)}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
          title="Edit this fact"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

function FactRow({
  fact,
  files,
  onConfirm,
  onEdit,
  editingFactId,
  onSaveEdit,
  onCancelEdit,
}: {
  fact: CaseFactInfo;
  files: CaseFileInfo[];
  onConfirm: (factId: string) => void;
  onEdit: (factId: string) => void;
  editingFactId: string | null;
  onSaveEdit: (factId: string, value: Record<string, unknown>, effectiveDate: string | null) => void;
  onCancelEdit: () => void;
}) {
  if (editingFactId === fact.id) {
    return (
      <FactEditForm
        fact={fact}
        onSave={(value, effectiveDate) => onSaveEdit(fact.id, value, effectiveDate)}
        onCancel={onCancelEdit}
      />
    );
  }

  const badge = confidenceBadge(fact.confidence);
  return (
    <div className="group flex items-start gap-2 rounded px-2 py-1.5 hover:bg-surface">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">
            {fact.fact_type.replace(/_/g, " ")}
          </span>
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
              badge === "high"
                ? "bg-green-100 text-green-700"
                : badge === "medium"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {Math.round(fact.confidence * 100)}%
          </span>
          <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-text-tertiary">
            {fact.extraction_method}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-text-secondary">
          {formatValue(fact.value)}
        </p>
        {fact.source_file_id && (
          <p className="mt-0.5 text-[10px] text-text-tertiary">
            Source: {sourceLabel(fact.source_file_id, files)}
          </p>
        )}
        {fact.effective_date && (
          <p className="mt-0.5 text-[10px] text-text-tertiary">
            Effective: {fact.effective_date}
          </p>
        )}
      </div>
      <div className="mt-0.5 flex shrink-0 items-center gap-1">
        {fact.confirmed ? (
          <span
            className="text-[10px] font-medium text-green-600"
            title="Confirmed"
          >
            Confirmed
          </span>
        ) : (
          <button
            onClick={() => onConfirm(fact.id)}
            className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
            title="Confirm this fact"
          >
            Confirm
          </button>
        )}
        <button
          onClick={() => onEdit(fact.id)}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-text-secondary opacity-0 transition-opacity hover:bg-accent-surface hover:text-accent group-hover:opacity-100"
          title="Edit this fact"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function CaseInfo({ caseId, files, onClose }: CaseInfoProps) {
  const [context, setContext] = useState<CaseContextInfo | null>(null);
  const [facts, setFacts] = useState<CaseFactInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingFactId, setEditingFactId] = useState<string | null>(null);
  const [addingCategory, setAddingCategory] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);
      const [ctx, factsResp] = await Promise.all([
        getCaseContext(caseId),
        listFacts(caseId),
      ]);
      setContext(ctx);
      setFacts(factsResp.facts);
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Failed to load case info"
      );
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleConfirm = useCallback(
    async (factId: string) => {
      try {
        const updated = await confirmFact(caseId, factId);
        setFacts((prev) =>
          prev.map((f) => (f.id === factId ? updated : f))
        );
      } catch {
        // Silently fail — fact may have been confirmed already
      }
    },
    [caseId]
  );

  const handleSaveEdit = useCallback(
    async (
      factId: string,
      value: Record<string, unknown>,
      effectiveDate: string | null,
    ) => {
      const fact = facts.find((f) => f.id === factId);
      if (!fact) return;

      try {
        const newFact = await supersedeFact(caseId, factId, {
          category: fact.category,
          fact_type: fact.fact_type,
          value,
          effective_date: effectiveDate,
        });
        // Replace old fact with new superseding fact
        setFacts((prev) =>
          prev.map((f) => (f.id === factId ? newFact : f))
        );
        setEditingFactId(null);
      } catch {
        // Keep edit form open on error
      }
    },
    [caseId, facts]
  );

  const handleAddFact = useCallback(
    async (
      category: string,
      factType: string,
      value: Record<string, unknown>,
      effectiveDate: string | null,
    ) => {
      try {
        const newFact = await addFact(caseId, {
          category,
          fact_type: factType,
          value,
          effective_date: effectiveDate,
        });
        setFacts((prev) => [...prev, newFact]);
        setAddingCategory(null);
      } catch {
        // Keep add form open on error
      }
    },
    [caseId]
  );

  const handleClaimStatusChange = useCallback(
    async (factId: string, newStatus: string) => {
      const fact = facts.find((f) => f.id === factId);
      if (!fact) return;

      const updatedValue = { ...fact.value, status: newStatus };
      try {
        const newFact = await supersedeFact(caseId, factId, {
          category: fact.category,
          fact_type: fact.fact_type,
          value: updatedValue,
          effective_date: fact.effective_date,
        });
        setFacts((prev) =>
          prev.map((f) => (f.id === factId ? newFact : f))
        );
      } catch {
        // Revert silently — dropdown will stay at old value on next render
      }
    },
    [caseId, facts]
  );

  // Group facts by category
  const factsByCategory = facts.reduce<Record<string, CaseFactInfo[]>>(
    (acc, f) => {
      const cat = f.category;
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(f);
      return acc;
    },
    {}
  );

  // Map category to display name
  const categoryLabels: Record<string, string> = {
    party: "Parties",
    employment: "Employment",
    claim: "Claims",
    date: "Key Dates",
    financial: "Financials",
    court: "Court",
    attorney: "Attorneys",
  };

  // Ordered section keys
  const sectionOrder = [
    "party",
    "court",
    "attorney",
    "employment",
    "claim",
    "date",
    "financial",
  ];

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <p className="text-sm text-text-tertiary">Loading case info...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-background px-4">
        <div className="rounded-lg border border-error-border bg-error-bg px-6 py-4 text-center">
          <p className="text-sm text-error-text">{error}</p>
          <button
            onClick={onClose}
            className="mt-3 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col bg-background" data-testid="case-info-panel">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">
            Case Info
          </h2>
          <p className="text-xs text-text-tertiary" data-testid="fact-count-indicator">
            {facts.length} facts \u00b7{" "}
            {facts.filter((f) => f.confirmed).length} of {facts.length} confirmed
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-text-tertiary transition-colors hover:bg-surface hover:text-text-primary"
          title="Close case info"
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
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {facts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-sm text-text-tertiary">
              No facts extracted yet.
            </p>
            <p className="mt-1 text-xs text-text-tertiary">
              Upload documents and the system will extract key facts
              automatically.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {sectionOrder.map((cat) => {
              const catFacts = factsByCategory[cat];
              return (
                <div key={cat}>
                  <SectionHeader
                    title={categoryLabels[cat] || cat}
                    count={catFacts?.length ?? 0}
                    onAdd={() => {
                      setEditingFactId(null);
                      setAddingCategory(cat);
                    }}
                  />
                  {!catFacts || catFacts.length === 0 ? (
                    addingCategory !== cat && <EmptySection />
                  ) : cat === "claim" ? (
                    <div className="mt-1 space-y-1.5">
                      {catFacts.map((fact) => (
                        <ClaimRow
                          key={fact.id}
                          fact={fact}
                          files={files}
                          onConfirm={handleConfirm}
                          onEdit={(id) => {
                            setAddingCategory(null);
                            setEditingFactId(id);
                          }}
                          editingFactId={editingFactId}
                          onSaveEdit={handleSaveEdit}
                          onCancelEdit={() => setEditingFactId(null)}
                          onStatusChange={handleClaimStatusChange}
                        />
                      ))}
                    </div>
                  ) : cat === "financial" ? (
                    <div className="mt-1 space-y-0.5" data-testid="financial-log">
                      {[...catFacts]
                        .sort((a, b) => {
                          const aDate = (a.value.date ? String(a.value.date) : a.effective_date) ?? "";
                          const bDate = (b.value.date ? String(b.value.date) : b.effective_date) ?? "";
                          return aDate.localeCompare(bDate);
                        })
                        .map((fact) => (
                          <FinancialRow
                            key={fact.id}
                            fact={fact}
                            files={files}
                            onConfirm={handleConfirm}
                            onEdit={(id) => {
                              setAddingCategory(null);
                              setEditingFactId(id);
                            }}
                            editingFactId={editingFactId}
                            onSaveEdit={handleSaveEdit}
                            onCancelEdit={() => setEditingFactId(null)}
                          />
                        ))}
                    </div>
                  ) : cat === "employment" ? (
                    <div className="mt-1 space-y-1.5" data-testid="employment-timeline">
                      {[...catFacts]
                        .sort((a, b) => {
                          const aDate = a.value.start_date ? String(a.value.start_date) : "";
                          const bDate = b.value.start_date ? String(b.value.start_date) : "";
                          return aDate.localeCompare(bDate);
                        })
                        .map((fact) => (
                          <EmploymentRow
                            key={fact.id}
                            fact={fact}
                            files={files}
                            onConfirm={handleConfirm}
                            onEdit={(id) => {
                              setAddingCategory(null);
                              setEditingFactId(id);
                            }}
                            editingFactId={editingFactId}
                            onSaveEdit={handleSaveEdit}
                            onCancelEdit={() => setEditingFactId(null)}
                          />
                        ))}
                    </div>
                  ) : (
                    <div className="mt-1 space-y-0.5">
                      {catFacts.map((fact) => (
                        <FactRow
                          key={fact.id}
                          fact={fact}
                          files={files}
                          onConfirm={handleConfirm}
                          onEdit={(id) => {
                            setAddingCategory(null);
                            setEditingFactId(id);
                          }}
                          editingFactId={editingFactId}
                          onSaveEdit={handleSaveEdit}
                          onCancelEdit={() => setEditingFactId(null)}
                        />
                      ))}
                    </div>
                  )}
                  {addingCategory === cat && (
                    <div className="mt-1">
                      <FactAddForm
                        category={cat}
                        onSave={(factType, value, effectiveDate) =>
                          handleAddFact(cat, factType, value, effectiveDate)
                        }
                        onCancel={() => setAddingCategory(null)}
                      />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Extraction sources */}
            {context?.extraction_sources &&
              Object.keys(context.extraction_sources).length > 0 && (
                <div>
                  <SectionHeader
                    title="Extraction Sources"
                    count={
                      Object.keys(context.extraction_sources).length
                    }
                  />
                  <div className="mt-1 space-y-1 px-2">
                    {Object.entries(context.extraction_sources).map(
                      ([fileId, methods]) => (
                        <div
                          key={fileId}
                          className="text-xs text-text-secondary"
                        >
                          <span className="font-medium">
                            {sourceLabel(fileId, files)}
                          </span>
                          <span className="ml-1 text-text-tertiary">
                            ({methods.join(", ")})
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
