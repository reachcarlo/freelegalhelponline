"use client";

import type {
  BankCategoryInfo,
  BankItemInfo,
  CaseInfo,
  DiscoveryRequest,
  DiscoveryToolType,
} from "@/lib/discovery-api";
import { TOOL_LABELS } from "@/lib/discovery-api";

// ── Types ────────────────────────────────────────────────────────────

interface PreviewPanelProps {
  toolType: DiscoveryToolType;
  caseInfo: CaseInfo;
  selectedClaims: string[];
  claimLabels: Record<string, string>;
  /** For FROGs: selected sections + bank data for labels */
  selectedSections?: string[];
  categories?: BankCategoryInfo[];
  items?: BankItemInfo[];
  /** For SROGs/RFPDs/RFAs: selected requests */
  selectedRequests?: DiscoveryRequest[];
  /** Custom definitions */
  definitions?: Record<string, string>;
  includeDefinitions?: boolean;
}

// ── Helpers ──────────────────────────────────────────────────────────

function SectionRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5 text-sm sm:flex-row sm:gap-2">
      <span className="text-text-tertiary shrink-0 text-xs sm:text-sm sm:w-36">{label}</span>
      <span className="text-text-primary break-words">{value}</span>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────

export default function PreviewPanel({
  toolType,
  caseInfo,
  selectedClaims,
  claimLabels,
  selectedSections,
  categories,
  items,
  selectedRequests,
  definitions,
  includeDefinitions,
}: PreviewPanelProps) {
  const isFrog = toolType.includes("frogs");

  // For FROGs: group selected items by category for display
  const sectionsByGroup = (() => {
    if (!isFrog || !selectedSections || !categories || !items) return [];
    const selectedSet = new Set(selectedSections);
    return categories
      .map((cat) => {
        const groupItems = (items || []).filter(
          (i) => i.category === cat.key && selectedSet.has(i.id)
        );
        return { category: cat, items: groupItems };
      })
      .filter((g) => g.items.length > 0);
  })();

  // For SROGs/RFPDs/RFAs: count selected
  const selectedRequestList = (selectedRequests || []).filter(
    (r) => r.is_selected
  );

  return (
    <div className="space-y-6">
      <h3 className="text-sm font-semibold text-text-primary">
        Review Before Generating
      </h3>

      {/* Document type */}
      <div className="rounded-lg border border-border p-4">
        <p className="text-xs text-text-tertiary mb-1">Document</p>
        <p className="text-sm font-medium text-text-primary">
          {TOOL_LABELS[toolType]}
        </p>
      </div>

      {/* Case info summary */}
      <div className="rounded-lg border border-border p-4 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
          Case Information
        </p>
        <SectionRow label="Case Number" value={caseInfo.case_number} />
        <SectionRow label="County" value={caseInfo.court_county} />
        <SectionRow label="Party Role" value={caseInfo.party_role === "plaintiff" ? "Plaintiff" : "Defendant"} />
        <SectionRow
          label="Plaintiff(s)"
          value={caseInfo.plaintiffs.map((p) => p.name).filter(Boolean).join(", ")}
        />
        <SectionRow
          label="Defendant(s)"
          value={caseInfo.defendants.map((d) => d.name).filter(Boolean).join(", ")}
        />
        <SectionRow
          label={caseInfo.attorney.is_pro_per ? "Pro Per" : "Attorney"}
          value={caseInfo.attorney.name}
        />
        {caseInfo.attorney.firm_name && (
          <SectionRow label="Firm" value={caseInfo.attorney.firm_name} />
        )}
        <SectionRow label="Judge" value={caseInfo.judge_name} />
        <SectionRow label="Department" value={caseInfo.department} />
        <SectionRow label="Filed" value={caseInfo.complaint_filed_date} />
        <SectionRow label="Trial Date" value={caseInfo.trial_date} />
        <SectionRow label="Set Number" value={String(caseInfo.set_number)} />
      </div>

      {/* Claims */}
      {selectedClaims.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Claims ({selectedClaims.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {selectedClaims.map((c) => (
              <span
                key={c}
                className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs text-text-secondary"
              >
                {claimLabels[c] || c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* FROG sections */}
      {isFrog && sectionsByGroup.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Selected Sections ({selectedSections?.length || 0})
          </p>
          <div className="space-y-3">
            {sectionsByGroup.map(({ category, items: groupItems }) => (
              <div key={category.key}>
                <p className="text-xs font-medium text-text-secondary mb-1">
                  {category.key}. {category.label}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {groupItems.map((item) => (
                    <span
                      key={item.id}
                      className="rounded bg-accent-surface px-2 py-0.5 text-xs text-accent font-mono"
                    >
                      {item.id}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SROGs/RFPDs/RFAs requests */}
      {!isFrog && selectedRequestList.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Selected Requests ({selectedRequestList.length})
          </p>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {selectedRequestList.map((req, i) => (
              <div
                key={req.id}
                className="rounded-md border border-border p-2 text-xs"
              >
                <span className="font-mono text-accent mr-2">
                  {i + 1}.
                </span>
                <span className="text-text-secondary line-clamp-2">
                  {req.text}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Definitions */}
      {definitions && Object.keys(definitions).length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
              Custom Definitions ({Object.keys(definitions).length})
            </p>
            {includeDefinitions !== undefined && (
              <span
                className={`text-xs ${
                  includeDefinitions ? "text-verified-text" : "text-text-tertiary"
                }`}
              >
                {includeDefinitions ? "Included" : "Excluded"}
              </span>
            )}
          </div>
          <div className="space-y-1">
            {Object.entries(definitions).map(([term, def]) => (
              <p key={term} className="text-xs text-text-secondary">
                <span className="font-medium text-text-primary">{term}:</span>{" "}
                {def.length > 80 ? `${def.slice(0, 80)}…` : def}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
