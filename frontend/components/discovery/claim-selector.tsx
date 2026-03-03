"use client";

import { useMemo } from "react";
import { groupClaimTypes } from "@/lib/discovery-api";

interface ClaimSelectorProps {
  selected: string[];
  onToggle: (claim: string) => void;
}

export default function ClaimSelector({
  selected,
  onToggle,
}: ClaimSelectorProps) {
  const groups = useMemo(() => groupClaimTypes(), []);

  return (
    <fieldset>
      <legend className="text-sm font-medium text-text-primary mb-1">
        Claim Types
      </legend>
      <p className="text-xs text-text-tertiary mb-4">
        Select all claims asserted in the case. This determines which discovery
        requests are suggested.
      </p>

      {selected.length === 0 && (
        <p className="text-xs text-error-text mb-3">
          Select at least one claim type to proceed.
        </p>
      )}

      <div className="space-y-5">
        {groups.map(({ group, claims }) => (
          <div key={group}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
              {group}
            </h3>
            <div className="flex flex-wrap gap-2">
              {claims.map((ct) => {
                const isSelected = selected.includes(ct.value);
                return (
                  <button
                    key={ct.value}
                    type="button"
                    onClick={() => onToggle(ct.value)}
                    aria-pressed={isSelected}
                    className={`min-h-[36px] rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
                      isSelected
                        ? "border-accent bg-accent-surface text-accent"
                        : "border-border text-text-secondary hover:border-border-hover hover:text-text-primary"
                    }`}
                  >
                    {ct.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {selected.length > 0 && (
        <p className="mt-3 text-xs text-text-tertiary">
          {selected.length} claim{selected.length !== 1 ? "s" : ""} selected
        </p>
      )}
    </fieldset>
  );
}
