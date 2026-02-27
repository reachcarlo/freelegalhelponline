"use client";

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
  if (sources.length === 0) return null;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="mb-2 text-sm font-semibold text-text-secondary">
        Sources ({sources.length})
      </h3>
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
  );
}
