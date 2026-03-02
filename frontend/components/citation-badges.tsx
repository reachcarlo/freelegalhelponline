"use client";

import { useState } from "react";
import type { CitationVerification } from "@/lib/api";

interface CitationBadgesProps {
  verifications: CitationVerification[];
}

const CONFIDENCE_CONFIG = {
  verified: {
    label: "Verified",
    bgClass: "bg-verified-bg",
    textClass: "text-verified-text",
    borderClass: "border-verified-border",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path
          d="M3 8.5l3 3 7-7"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  unverified: {
    label: "Unverified",
    bgClass: "bg-unverified-bg",
    textClass: "text-unverified-text",
    borderClass: "border-unverified-border",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M8 5v3"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="8" cy="11" r="0.75" fill="currentColor" />
      </svg>
    ),
  },
  suspicious: {
    label: "Suspicious",
    bgClass: "bg-suspicious-bg",
    textClass: "text-suspicious-text",
    borderClass: "border-suspicious-border",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2L1.5 13h13L8 2z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path
          d="M8 6.5v3"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="8" cy="11.5" r="0.75" fill="currentColor" />
      </svg>
    ),
  },
} as const;

export default function CitationBadges({
  verifications,
}: CitationBadgesProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (verifications.length === 0) return null;

  // Count by confidence level
  const counts = { verified: 0, unverified: 0, suspicious: 0 };
  for (const v of verifications) {
    counts[v.confidence]++;
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="mb-2 flex items-center gap-2">
        <h4 className="text-xs font-semibold text-text-secondary">
          Citation Verification
        </h4>
        {/* Summary counts */}
        <div className="flex gap-1.5">
          {counts.verified > 0 && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-verified-bg px-1.5 py-0.5 text-[10px] font-medium text-verified-text">
              {CONFIDENCE_CONFIG.verified.icon}
              {counts.verified}
            </span>
          )}
          {counts.unverified > 0 && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-unverified-bg px-1.5 py-0.5 text-[10px] font-medium text-unverified-text">
              {CONFIDENCE_CONFIG.unverified.icon}
              {counts.unverified}
            </span>
          )}
          {counts.suspicious > 0 && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-suspicious-bg px-1.5 py-0.5 text-[10px] font-medium text-suspicious-text">
              {CONFIDENCE_CONFIG.suspicious.icon}
              {counts.suspicious}
            </span>
          )}
        </div>
      </div>

      <ul className="space-y-1">
        {verifications.map((v, i) => {
          const config = CONFIDENCE_CONFIG[v.confidence];
          const isExpanded = expandedIdx === i;

          return (
            <li key={i}>
              <button
                onClick={() => setExpandedIdx(isExpanded ? null : i)}
                className={`flex w-full min-h-[44px] items-center gap-2 rounded border px-2.5 py-1.5 text-left text-xs transition-colors ${config.bgClass} ${config.borderClass} ${config.textClass} hover:opacity-80`}
                aria-expanded={isExpanded}
              >
                <span className="shrink-0">{config.icon}</span>
                <span className="min-w-0 flex-1 truncate font-medium">
                  {v.citation_text}
                </span>
                <span className="shrink-0 rounded bg-surface/50 px-1.5 py-0.5 text-[10px]">
                  {v.citation_type}
                </span>
              </button>
              {isExpanded && v.detail && (
                <p className="mt-0.5 px-2.5 text-[11px] text-text-tertiary">
                  {v.detail}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
