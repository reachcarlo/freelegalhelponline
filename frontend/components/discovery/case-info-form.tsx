"use client";

import { useCallback } from "react";
import type { AttorneyInfo, CaseInfo, PartyInfo } from "@/lib/discovery-api";

// ── California counties ─────────────────────────────────────────────

const CA_COUNTIES = [
  "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa",
  "Contra Costa", "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt",
  "Imperial", "Inyo", "Kern", "Kings", "Lake", "Lassen", "Los Angeles",
  "Madera", "Marin", "Mariposa", "Mendocino", "Merced", "Modoc", "Mono",
  "Monterey", "Napa", "Nevada", "Orange", "Placer", "Plumas", "Riverside",
  "Sacramento", "San Benito", "San Bernardino", "San Diego",
  "San Francisco", "San Joaquin", "San Luis Obispo", "San Mateo",
  "Santa Barbara", "Santa Clara", "Santa Cruz", "Shasta", "Sierra",
  "Siskiyou", "Solano", "Sonoma", "Stanislaus", "Sutter", "Tehama",
  "Trinity", "Tulare", "Tuolumne", "Ventura", "Yolo", "Yuba",
];

// ── Sub-components ──────────────────────────────────────────────────

function FormField({
  label,
  htmlFor,
  required,
  children,
}: {
  label: string;
  htmlFor: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1 block text-xs font-medium text-text-secondary"
      >
        {label}
        {required && <span className="text-error-text ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none transition-colors";

const selectCls = `${inputCls} appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_8px_center] bg-no-repeat pr-8`;

// ── Party list editor ───────────────────────────────────────────────

function PartyListEditor({
  label,
  parties,
  onChange,
  idPrefix,
}: {
  label: string;
  parties: PartyInfo[];
  onChange: (parties: PartyInfo[]) => void;
  idPrefix: string;
}) {
  const updateParty = (index: number, field: keyof PartyInfo, value: string | boolean) => {
    const next = parties.map((p, i) =>
      i === index ? { ...p, [field]: value } : p
    );
    onChange(next);
  };

  const addParty = () => {
    if (parties.length >= 10) return;
    onChange([...parties, { name: "", is_entity: false, entity_type: null }]);
  };

  const removeParty = (index: number) => {
    if (parties.length <= 1) return;
    onChange(parties.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-text-secondary">
          {label}
          <span className="text-error-text ml-0.5">*</span>
        </span>
        {parties.length < 10 && (
          <button
            type="button"
            onClick={addParty}
            className="text-xs text-accent hover:text-accent-hover transition-colors"
          >
            + Add party
          </button>
        )}
      </div>
      <div className="space-y-3">
        {parties.map((party, i) => (
          <div key={i} className="flex gap-2 items-start">
            <div className="flex-1 space-y-2">
              <input
                id={`${idPrefix}-${i}-name`}
                type="text"
                value={party.name}
                onChange={(e) => updateParty(i, "name", e.target.value)}
                placeholder={`${label} name`}
                className={inputCls}
                required
              />
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 text-xs text-text-tertiary cursor-pointer">
                  <input
                    type="checkbox"
                    checked={party.is_entity}
                    onChange={(e) => updateParty(i, "is_entity", e.target.checked)}
                    className="rounded border-border"
                  />
                  Entity
                </label>
                {party.is_entity && (
                  <input
                    type="text"
                    value={party.entity_type || ""}
                    onChange={(e) =>
                      updateParty(i, "entity_type", e.target.value || null as unknown as string)
                    }
                    placeholder="e.g. Corporation"
                    className={`${inputCls} max-w-[160px] text-xs`}
                  />
                )}
              </div>
            </div>
            {parties.length > 1 && (
              <button
                type="button"
                onClick={() => removeParty(i)}
                className="mt-2 min-h-[28px] min-w-[28px] rounded text-text-tertiary hover:text-error-text transition-colors"
                aria-label={`Remove ${label} ${i + 1}`}
              >
                &times;
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main form ───────────────────────────────────────────────────────

interface CaseInfoFormProps {
  caseInfo: CaseInfo;
  onCaseInfoChange: (info: Partial<CaseInfo>) => void;
  onPlaintiffsChange: (parties: PartyInfo[]) => void;
  onDefendantsChange: (parties: PartyInfo[]) => void;
  onAttorneyChange: (info: Partial<AttorneyInfo>) => void;
  errors?: Record<string, string>;
}

export default function CaseInfoForm({
  caseInfo,
  onCaseInfoChange,
  onPlaintiffsChange,
  onDefendantsChange,
  onAttorneyChange,
  errors,
}: CaseInfoFormProps) {
  const setField = useCallback(
    (field: keyof CaseInfo, value: string | boolean | number | null) =>
      onCaseInfoChange({ [field]: value }),
    [onCaseInfoChange]
  );

  const setAtty = useCallback(
    (field: keyof AttorneyInfo, value: string | boolean | null) =>
      onAttorneyChange({ [field]: value }),
    [onAttorneyChange]
  );

  return (
    <div className="space-y-6">
      {/* ── Case identification ── */}
      <section>
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Case Information
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Case Number" htmlFor="case_number" required>
            <input
              id="case_number"
              type="text"
              value={caseInfo.case_number}
              onChange={(e) => setField("case_number", e.target.value)}
              placeholder="e.g. 24STCV12345"
              className={inputCls}
            />
            {errors?.case_number && (
              <p className="mt-1 text-xs text-error-text">{errors.case_number}</p>
            )}
          </FormField>

          <FormField label="County" htmlFor="court_county" required>
            <select
              id="court_county"
              value={caseInfo.court_county}
              onChange={(e) => setField("court_county", e.target.value)}
              className={selectCls}
            >
              <option value="">Select county…</option>
              {CA_COUNTIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Judge" htmlFor="judge_name">
            <input
              id="judge_name"
              type="text"
              value={caseInfo.judge_name || ""}
              onChange={(e) => setField("judge_name", e.target.value || null)}
              placeholder="Hon. Judge Name"
              className={inputCls}
            />
          </FormField>

          <FormField label="Department" htmlFor="department">
            <input
              id="department"
              type="text"
              value={caseInfo.department || ""}
              onChange={(e) => setField("department", e.target.value || null)}
              placeholder="e.g. 24"
              className={inputCls}
            />
          </FormField>

          <FormField label="Complaint Filed Date" htmlFor="complaint_filed_date">
            <input
              id="complaint_filed_date"
              type="date"
              value={caseInfo.complaint_filed_date || ""}
              onChange={(e) =>
                setField("complaint_filed_date", e.target.value || null)
              }
              className={inputCls}
            />
          </FormField>

          <FormField label="Trial Date" htmlFor="trial_date">
            <input
              id="trial_date"
              type="date"
              value={caseInfo.trial_date || ""}
              onChange={(e) => setField("trial_date", e.target.value || null)}
              className={inputCls}
            />
          </FormField>

          <FormField label="Set Number" htmlFor="set_number">
            <input
              id="set_number"
              type="number"
              min={1}
              max={10}
              value={caseInfo.set_number}
              onChange={(e) =>
                setField("set_number", Math.max(1, Math.min(10, Number(e.target.value))))
              }
              className={inputCls}
            />
          </FormField>

          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer pb-2">
              <input
                type="checkbox"
                checked={caseInfo.does_included}
                onChange={(e) => setField("does_included", e.target.checked)}
                className="rounded border-border"
              />
              Include Does 1-50
            </label>
          </div>
        </div>
      </section>

      {/* ── Parties ── */}
      <section>
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Parties
        </h3>
        <div className="space-y-4">
          <PartyListEditor
            label="Plaintiff"
            parties={caseInfo.plaintiffs}
            onChange={onPlaintiffsChange}
            idPrefix="plaintiff"
          />
          <PartyListEditor
            label="Defendant"
            parties={caseInfo.defendants}
            onChange={onDefendantsChange}
            idPrefix="defendant"
          />
        </div>
      </section>

      {/* ── Attorney / Pro Per ── */}
      <section>
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Attorney Information
        </h3>

        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer mb-3">
          <input
            type="checkbox"
            checked={caseInfo.attorney.is_pro_per}
            onChange={(e) => setAtty("is_pro_per", e.target.checked)}
            className="rounded border-border"
          />
          Self-represented (Pro Per)
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Name" htmlFor="atty_name" required>
            <input
              id="atty_name"
              type="text"
              value={caseInfo.attorney.name}
              onChange={(e) => setAtty("name", e.target.value)}
              placeholder={caseInfo.attorney.is_pro_per ? "Your full name" : "Attorney name"}
              className={inputCls}
            />
            {errors?.attorney_name && (
              <p className="mt-1 text-xs text-error-text">{errors.attorney_name}</p>
            )}
          </FormField>

          <FormField label="State Bar Number" htmlFor="atty_sbn">
            <input
              id="atty_sbn"
              type="text"
              value={caseInfo.attorney.sbn}
              onChange={(e) => setAtty("sbn", e.target.value)}
              placeholder={caseInfo.attorney.is_pro_per ? "N/A" : "e.g. 123456"}
              className={inputCls}
            />
          </FormField>

          {!caseInfo.attorney.is_pro_per && (
            <FormField label="Firm Name" htmlFor="atty_firm">
              <input
                id="atty_firm"
                type="text"
                value={caseInfo.attorney.firm_name || ""}
                onChange={(e) => setAtty("firm_name", e.target.value || null)}
                placeholder="Law firm name"
                className={inputCls}
              />
            </FormField>
          )}

          <FormField label="Attorney For" htmlFor="atty_for">
            <input
              id="atty_for"
              type="text"
              value={caseInfo.attorney.attorney_for}
              onChange={(e) => setAtty("attorney_for", e.target.value)}
              placeholder="e.g. Plaintiff Jane Doe"
              className={inputCls}
            />
          </FormField>

          <FormField label="Address" htmlFor="atty_address" required>
            <input
              id="atty_address"
              type="text"
              value={caseInfo.attorney.address}
              onChange={(e) => setAtty("address", e.target.value)}
              placeholder="Street address"
              className={inputCls}
            />
          </FormField>

          <FormField label="City, State, ZIP" htmlFor="atty_csz" required>
            <input
              id="atty_csz"
              type="text"
              value={caseInfo.attorney.city_state_zip}
              onChange={(e) => setAtty("city_state_zip", e.target.value)}
              placeholder="City, CA 90001"
              className={inputCls}
            />
          </FormField>

          <FormField label="Phone" htmlFor="atty_phone" required>
            <input
              id="atty_phone"
              type="tel"
              value={caseInfo.attorney.phone}
              onChange={(e) => setAtty("phone", e.target.value)}
              placeholder="(555) 123-4567"
              className={inputCls}
            />
          </FormField>

          <FormField label="Email" htmlFor="atty_email" required>
            <input
              id="atty_email"
              type="email"
              value={caseInfo.attorney.email}
              onChange={(e) => setAtty("email", e.target.value)}
              placeholder="attorney@example.com"
              className={inputCls}
            />
          </FormField>

          <FormField label="Fax" htmlFor="atty_fax">
            <input
              id="atty_fax"
              type="tel"
              value={caseInfo.attorney.fax || ""}
              onChange={(e) => setAtty("fax", e.target.value || null)}
              placeholder="(555) 123-4568"
              className={inputCls}
            />
          </FormField>
        </div>
      </section>
    </div>
  );
}
