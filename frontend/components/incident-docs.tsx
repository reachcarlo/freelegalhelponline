"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  getIncidentGuide,
  type DocumentationFieldInfo,
  type EvidenceItemInfo,
  type IncidentDocResponse,
} from "@/lib/calculators/incident-docs";

const INCIDENT_TYPES = [
  { value: "unpaid_wages", label: "Unpaid Wages" },
  { value: "discrimination", label: "Discrimination" },
  { value: "harassment", label: "Harassment / Hostile Work Environment" },
  { value: "wrongful_termination", label: "Wrongful Termination" },
  { value: "retaliation", label: "Retaliation" },
  { value: "family_medical_leave", label: "Family / Medical Leave Violation" },
  { value: "workplace_safety", label: "Workplace Safety / Health Hazard" },
  { value: "misclassification", label: "Worker Misclassification" },
  { value: "meal_rest_breaks", label: "Meal / Rest Break Violations" },
  { value: "whistleblower", label: "Whistleblower" },
] as const;

const STORAGE_KEY = "employee_help_incidents";

interface StoredIncident {
  id: string;
  incident_type: string;
  incident_type_label: string;
  created_at: string;
  updated_at: string;
  fields: Record<string, string>;
  evidence_checked: string[];
}

function loadIncidents(): StoredIncident[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveIncidents(incidents: StoredIncident[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(incidents));
}

const inputClasses =
  "w-full min-h-[44px] rounded-lg border border-border bg-input-bg px-3 py-2 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent";

function renderField(
  field: DocumentationFieldInfo,
  value: string,
  onChange: (name: string, val: string) => void
) {
  const baseId = `field-${field.name}`;

  switch (field.field_type) {
    case "textarea":
      return (
        <textarea
          id={baseId}
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
          rows={3}
          className={inputClasses + " resize-y"}
        />
      );
    case "date":
      return (
        <input
          id={baseId}
          type="date"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          required={field.required}
          className={inputClasses}
        />
      );
    case "time":
      return (
        <input
          id={baseId}
          type="time"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          className={inputClasses}
        />
      );
    case "number":
      return (
        <input
          id={baseId}
          type="number"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
          min="0"
          className={inputClasses}
        />
      );
    case "select":
      return (
        <select
          id={baseId}
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          required={field.required}
          className={inputClasses}
        >
          <option value="">Select...</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    case "boolean":
      return (
        <div className="flex items-center gap-2 min-h-[44px]">
          <input
            id={baseId}
            type="checkbox"
            checked={value === "true"}
            onChange={(e) =>
              onChange(field.name, e.target.checked ? "true" : "false")
            }
            className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
          />
          <label htmlFor={baseId} className="text-sm text-text-secondary">
            Yes
          </label>
        </div>
      );
    default:
      return (
        <input
          id={baseId}
          type="text"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
          className={inputClasses}
        />
      );
  }
}

function importanceBadge(importance: EvidenceItemInfo["importance"]) {
  switch (importance) {
    case "critical":
      return (
        <span className="inline-flex items-center rounded-full bg-error-bg border border-error-border px-2 py-0.5 text-xs font-medium text-error-text">
          Critical
        </span>
      );
    case "recommended":
      return (
        <span className="inline-flex items-center rounded-full bg-accent-surface border border-accent px-2 py-0.5 text-xs font-medium text-accent">
          Recommended
        </span>
      );
    case "optional":
      return (
        <span className="inline-flex items-center rounded-full bg-badge-bg border border-border px-2 py-0.5 text-xs font-medium text-text-secondary">
          Optional
        </span>
      );
  }
}

type Step = "select" | "form" | "evidence" | "timeline";

export default function IncidentDocs() {
  const [step, setStep] = useState<Step>("select");
  const [incidentType, setIncidentType] = useState("");
  const [guide, setGuide] = useState<IncidentDocResponse | null>(null);
  const [error, setError] = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [checkedEvidence, setCheckedEvidence] = useState<Set<string>>(
    new Set()
  );
  const [savedIncidents, setSavedIncidents] = useState<StoredIncident[]>(loadIncidents);
  const [editingId, setEditingId] = useState<string | null>(null);

  const handleFieldChange = useCallback((name: string, val: string) => {
    setFieldValues((prev) => ({ ...prev, [name]: val }));
  }, []);

  function handleStart() {
    if (!incidentType) return;

    setError("");

    try {
      const data = getIncidentGuide(incidentType);
      setGuide(data);
      setFieldValues({});
      setCheckedEvidence(new Set());
      setEditingId(null);
      setStep("form");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  function handleToggleEvidence(description: string) {
    setCheckedEvidence((prev) => {
      const next = new Set(prev);
      if (next.has(description)) {
        next.delete(description);
      } else {
        next.add(description);
      }
      return next;
    });
  }

  function handleSave() {
    if (!guide) return;

    const now = new Date().toISOString();
    const incidents = loadIncidents();

    if (editingId) {
      const idx = incidents.findIndex((inc) => inc.id === editingId);
      if (idx >= 0) {
        incidents[idx] = {
          ...incidents[idx],
          updated_at: now,
          fields: { ...fieldValues },
          evidence_checked: Array.from(checkedEvidence),
        };
      }
    } else {
      incidents.push({
        id: crypto.randomUUID(),
        incident_type: guide.incident_type,
        incident_type_label: guide.incident_type_label,
        created_at: now,
        updated_at: now,
        fields: { ...fieldValues },
        evidence_checked: Array.from(checkedEvidence),
      });
    }

    saveIncidents(incidents);
    setSavedIncidents(incidents);
    setStep("timeline");
  }

  function handleEdit(incident: StoredIncident) {
    setIncidentType(incident.incident_type);
    setEditingId(incident.id);

    try {
      const data = getIncidentGuide(incident.incident_type);
      setGuide(data);
      setFieldValues({ ...incident.fields });
      setCheckedEvidence(new Set(incident.evidence_checked));
      setStep("form");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  function handleDelete(id: string) {
    const incidents = loadIncidents().filter((inc) => inc.id !== id);
    saveIncidents(incidents);
    setSavedIncidents(incidents);
  }

  function handleExport() {
    const incidents = loadIncidents();
    if (incidents.length === 0) return;

    const lines: string[] = [
      "PERSONAL INCIDENT DOCUMENTATION RECORD",
      "========================================",
      "",
      "DISCLAIMER: This is a personal record of workplace incidents.",
      "It is NOT a legal document and does not constitute legal advice.",
      "Consult a licensed California employment attorney for advice about your specific situation.",
      "",
      `Generated: ${new Date().toLocaleString()}`,
      `Total incidents: ${incidents.length}`,
      "",
    ];

    for (const incident of incidents) {
      lines.push("---");
      lines.push(`Type: ${incident.incident_type_label}`);
      lines.push(`Created: ${new Date(incident.created_at).toLocaleString()}`);
      lines.push(
        `Last updated: ${new Date(incident.updated_at).toLocaleString()}`
      );
      lines.push("");

      for (const [key, value] of Object.entries(incident.fields)) {
        if (value && value !== "false") {
          const label = key
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase());
          lines.push(`${label}: ${value === "true" ? "Yes" : value}`);
        }
      }

      if (incident.evidence_checked.length > 0) {
        lines.push("");
        lines.push("Evidence collected:");
        for (const item of incident.evidence_checked) {
          lines.push(`  [x] ${item}`);
        }
      }

      lines.push("");
    }

    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `incident-records-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleNewIncident() {
    setStep("select");
    setGuide(null);
    setIncidentType("");
    setFieldValues({});
    setCheckedEvidence(new Set());
    setEditingId(null);
    setError("");
  }

  // ── Step 1: Select type ──────────────────────────────────────────

  if (step === "select") {
    return (
      <div>
        <div className="space-y-4">
          <div>
            <label
              htmlFor="incident-type"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              What type of incident do you want to document?
            </label>
            <select
              id="incident-type"
              value={incidentType}
              onChange={(e) => setIncidentType(e.target.value)}
              className={inputClasses}
              required
            >
              <option value="">Select an incident type...</option>
              {INCIDENT_TYPES.map((it) => (
                <option key={it.value} value={it.value}>
                  {it.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleStart}
            disabled={!incidentType}
            className="min-h-[44px] w-full rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Documenting
          </button>

          {savedIncidents.length > 0 && (
            <button
              onClick={() => setStep("timeline")}
              className="min-h-[44px] w-full rounded-lg border border-border bg-surface-raised px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:border-border-hover hover:bg-accent-surface"
            >
              View saved incidents ({savedIncidents.length})
            </button>
          )}
        </div>

        {error && (
          <div className="mt-6 rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
            {error}
          </div>
        )}
      </div>
    );
  }

  // ── Step 2: Guided form ──────────────────────────────────────────

  if (step === "form" && guide) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            {editingId ? "Edit" : "Document"}: {guide.incident_type_label}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {guide.description}
          </p>
        </div>

        {/* Guiding prompts */}
        <div className="rounded-lg border border-accent bg-accent-surface p-4">
          <p className="text-sm font-medium text-accent mb-2">
            Questions to guide your documentation:
          </p>
          <ul className="space-y-1">
            {guide.prompts.map((prompt, i) => (
              <li key={i} className="text-sm text-text-secondary">
                &bull; {prompt}
              </li>
            ))}
          </ul>
        </div>

        {/* Legal tips */}
        {guide.legal_tips.length > 0 && (
          <div className="rounded-lg border border-warning-border bg-warning-bg p-4">
            <p className="text-sm font-medium text-warning-text mb-2">
              Important legal context:
            </p>
            {guide.legal_tips.map((tip, i) => (
              <p key={i} className="text-sm text-warning-text mt-1">
                {tip}
              </p>
            ))}
          </div>
        )}

        {/* Common fields */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-tertiary uppercase tracking-wide">
            Basic Information
          </h3>
          {guide.common_fields.map((field) => (
            <div key={field.name}>
              <label
                htmlFor={`field-${field.name}`}
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                {field.label}
                {field.required && (
                  <span className="text-error-text ml-1">*</span>
                )}
              </label>
              {field.help_text && (
                <p className="text-xs text-text-tertiary mb-1">
                  {field.help_text}
                </p>
              )}
              {renderField(
                field,
                fieldValues[field.name] || "",
                handleFieldChange
              )}
            </div>
          ))}
        </div>

        {/* Specific fields */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-tertiary uppercase tracking-wide">
            {guide.incident_type_label}-Specific Details
          </h3>
          {guide.specific_fields.map((field) => (
            <div key={field.name}>
              <label
                htmlFor={`field-${field.name}`}
                className="block text-sm font-medium text-text-secondary mb-1"
              >
                {field.label}
                {field.required && (
                  <span className="text-error-text ml-1">*</span>
                )}
              </label>
              {field.help_text && (
                <p className="text-xs text-text-tertiary mb-1">
                  {field.help_text}
                </p>
              )}
              {renderField(
                field,
                fieldValues[field.name] || "",
                handleFieldChange
              )}
            </div>
          ))}
        </div>

        {/* Navigation */}
        <div className="flex gap-3">
          <button
            onClick={() => {
              setStep("select");
              setGuide(null);
              setEditingId(null);
            }}
            className="min-h-[44px] flex-1 rounded-lg border border-border bg-surface-raised px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:border-border-hover"
          >
            Back
          </button>
          <button
            onClick={() => setStep("evidence")}
            className="min-h-[44px] flex-1 rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover"
          >
            Continue to Evidence Checklist
          </button>
        </div>
      </div>
    );
  }

  // ── Step 3: Evidence checklist ────────────────────────────────────

  if (step === "evidence" && guide) {
    const grouped = {
      critical: guide.evidence_checklist.filter(
        (e) => e.importance === "critical"
      ),
      recommended: guide.evidence_checklist.filter(
        (e) => e.importance === "recommended"
      ),
      optional: guide.evidence_checklist.filter(
        (e) => e.importance === "optional"
      ),
    };

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            Evidence Checklist: {guide.incident_type_label}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            Check off evidence you have collected or plan to collect.
          </p>
        </div>

        {(["critical", "recommended", "optional"] as const).map((level) =>
          grouped[level].length > 0 ? (
            <div key={level} className="space-y-2">
              <h3 className="text-sm font-semibold text-text-tertiary uppercase tracking-wide flex items-center gap-2">
                {importanceBadge(level)}{" "}
                {level.charAt(0).toUpperCase() + level.slice(1)} Evidence
              </h3>
              {grouped[level].map((item) => (
                <label
                  key={item.description}
                  className="flex items-start gap-3 rounded-lg border border-border bg-surface-raised p-3 cursor-pointer hover:border-border-hover transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={checkedEvidence.has(item.description)}
                    onChange={() => handleToggleEvidence(item.description)}
                    className="mt-0.5 h-5 w-5 rounded border-border text-accent focus:ring-accent flex-shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="text-sm text-text-primary">
                      {item.description}
                    </p>
                    {item.tip && (
                      <p className="mt-1 text-xs text-text-tertiary italic">
                        Tip: {item.tip}
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          ) : null
        )}

        {/* Navigation */}
        <div className="flex gap-3">
          <button
            onClick={() => setStep("form")}
            className="min-h-[44px] flex-1 rounded-lg border border-border bg-surface-raised px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:border-border-hover"
          >
            Back
          </button>
          <button
            onClick={handleSave}
            className="min-h-[44px] flex-1 rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover"
          >
            {editingId ? "Update Incident" : "Save Incident"}
          </button>
        </div>
      </div>
    );
  }

  // ── Step 4: Timeline ─────────────────────────────────────────────

  if (step === "timeline") {
    const sorted = [...savedIncidents].sort(
      (a, b) =>
        new Date(b.fields.incident_date || b.created_at).getTime() -
        new Date(a.fields.incident_date || a.created_at).getTime()
    );

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">
            Your Incident Records ({savedIncidents.length})
          </h2>
        </div>

        {sorted.length === 0 ? (
          <p className="text-sm text-text-tertiary">
            No incidents documented yet.
          </p>
        ) : (
          <div className="space-y-3">
            {sorted.map((incident) => (
              <div
                key={incident.id}
                className="rounded-lg border border-border bg-surface-raised p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center rounded-full bg-accent-surface border border-accent px-2.5 py-0.5 text-xs font-medium text-accent">
                        {incident.incident_type_label}
                      </span>
                      {incident.fields.incident_date && (
                        <span className="text-xs text-text-tertiary">
                          {new Date(
                            incident.fields.incident_date + "T00:00:00"
                          ).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    {incident.fields.narrative && (
                      <p className="mt-2 text-sm text-text-secondary line-clamp-2">
                        {incident.fields.narrative}
                      </p>
                    )}
                    {incident.evidence_checked.length > 0 && (
                      <p className="mt-1 text-xs text-text-tertiary">
                        {incident.evidence_checked.length} evidence item
                        {incident.evidence_checked.length !== 1 ? "s" : ""}{" "}
                        checked
                      </p>
                    )}
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <button
                    onClick={() => handleEdit(incident)}
                    className="min-h-[44px] rounded-lg border border-border px-3 py-1.5 text-sm text-text-primary transition-colors hover:border-border-hover hover:bg-accent-surface"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(incident.id)}
                    className="min-h-[44px] rounded-lg border border-error-border px-3 py-1.5 text-sm text-error-text transition-colors hover:bg-error-bg"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="space-y-3">
          <button
            onClick={handleNewIncident}
            className="min-h-[44px] w-full rounded-lg bg-accent px-4 py-2 font-medium text-white transition-colors hover:bg-accent-hover"
          >
            Document Another Incident
          </button>

          {sorted.length > 0 && (
            <button
              onClick={handleExport}
              className="min-h-[44px] w-full rounded-lg border border-border bg-surface-raised px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:border-border-hover hover:bg-accent-surface"
            >
              Export All as Text File
            </button>
          )}
        </div>

        {/* Cross-links */}
        <div className="flex flex-wrap gap-3 text-sm">
          <Link
            href="/tools/deadline-calculator"
            className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
          >
            Check your filing deadlines &rarr;
          </Link>
          <Link
            href="/tools/agency-routing"
            className="min-h-[44px] inline-flex items-center text-accent hover:text-accent-hover"
          >
            Find the right agency &rarr;
          </Link>
        </div>
      </div>
    );
  }

  return null;
}
