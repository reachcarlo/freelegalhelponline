"use client";

import { useState } from "react";
import type { SourceInfo } from "@/lib/api";

interface SourceListProps {
  sources: SourceInfo[];
}

/** Map content_category to a human-readable label. */
function categoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    statute: "Statute",
    regulation: "Regulation",
    agency_guidance: "Agency Guidance",
    fact_sheet: "Fact Sheet",
    faq: "FAQ",
    policy: "Policy",
    jury_instruction: "CACI",
    case_law: "Case Law",
  };
  return labels[cat] || cat;
}

/** Build a display label for a source. */
function sourceLabel(source: SourceInfo): string {
  if (source.citation) return source.citation;
  if (source.heading_path) {
    const parts = source.heading_path.split(" > ");
    if (parts.length > 2) {
      return `${parts[0]} > ... > ${parts[parts.length - 1]}`;
    }
    return source.heading_path;
  }
  return `Chunk #${source.chunk_id}`;
}

export default function SourceList({ sources }: SourceListProps) {
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-text-tertiary transition-colors hover:border-border-hover hover:text-text-secondary"
        aria-expanded={expanded}
      >
        {sources.length} {sources.length === 1 ? "source" : "sources"}
        <svg
          width="10"
          height="10"
          viewBox="0 0 16 16"
          fill="none"
          className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {expanded && (
        <div className="mt-2 rounded-lg border border-border bg-surface p-4 animate-fade-in">
          <ul className="space-y-1">
            {sources.map((source, i) => (
              <li key={source.chunk_id || i} className="text-sm text-text-secondary">
                <span className="mr-2 inline-block rounded bg-badge-bg px-1.5 py-0.5 text-xs font-medium text-badge-text">
                  {categoryLabel(source.content_category)}
                </span>
                {source.source_url ? (
                  <a
                    href={source.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent underline hover:text-accent-hover"
                  >
                    {sourceLabel(source)}
                  </a>
                ) : (
                  <span>{sourceLabel(source)}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
