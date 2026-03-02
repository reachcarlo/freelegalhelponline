"use client";

import { useCallback, useState } from "react";
import type { AskMetadata, SourceInfo } from "@/lib/api";
import AnswerDisplay from "./answer-display";
import CitationBadges from "./citation-badges";
import FeedbackButtons from "./feedback-buttons";
import SourceList from "./source-list";

interface ConversationTurnProps {
  query: string;
  answer: string;
  sources: SourceInfo[];
  metadata: AskMetadata | null;
  isStreaming: boolean;
  isLatest: boolean;
  mode?: "consumer" | "attorney";
}

export default function ConversationTurnView({
  query,
  answer,
  sources,
  metadata,
  isStreaming,
  isLatest,
  mode,
}: ConversationTurnProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(answer);
    } catch {
      // Legacy fallback
      const ta = document.createElement("textarea");
      ta.value = answer;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [answer]);

  return (
    <div className="flex flex-col gap-3">
      {/* User query bubble */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-accent/10 px-4 py-3 text-sm text-text-primary">
          {query}
        </div>
      </div>

      {/* AI answer with identity marker + copy button */}
      {(answer || isStreaming) && (
        <div className="flex flex-col gap-2">
          {/* AI identity */}
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-accent">
                <path
                  d="M8 2l1.5 4.5L14 8l-4.5 1.5L8 14l-1.5-4.5L2 8l4.5-1.5L8 2z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <span className="text-xs font-medium text-text-tertiary">AI</span>
          </div>

          <div className="group relative">
            <AnswerDisplay text={answer} isStreaming={isStreaming} mode={mode} />
            {answer && !isStreaming && (
              <button
                onClick={handleCopy}
                className="absolute right-2 top-2 rounded-md border border-border bg-surface p-1.5
                           opacity-0 transition-opacity group-hover:opacity-100 max-sm:opacity-100
                           focus:outline-none focus:ring-2 focus:ring-accent/20"
                aria-label={copied ? "Copied" : "Copy answer"}
              >
                {copied ? (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    className="text-feedback-text-up"
                  >
                    <path
                      d="M3 8.5l3 3 7-7"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    className="text-text-tertiary"
                  >
                    <rect
                      x="5"
                      y="5"
                      width="8"
                      height="8"
                      rx="1.5"
                      stroke="currentColor"
                      strokeWidth="1.5"
                    />
                    <path
                      d="M3 11V3.5A.5.5 0 013.5 3H11"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Sources — collapsed chip, only after streaming completes */}
      {!isStreaming && sources.length > 0 && <SourceList sources={sources} />}

      {/* Citation verification badges — attorney mode only */}
      {answer &&
        !isStreaming &&
        mode === "attorney" &&
        metadata?.citation_verifications &&
        metadata.citation_verifications.length > 0 && (
          <CitationBadges verifications={metadata.citation_verifications} />
        )}

      {/* Feedback — only on the latest completed turn */}
      {isLatest && metadata && !isStreaming && metadata.query_id && (
        <FeedbackButtons queryId={metadata.query_id} />
      )}

      {/* Metadata — attorney mode only, collapsible */}
      {isLatest &&
        metadata &&
        !isStreaming &&
        mode === "attorney" &&
        (metadata.model ||
          metadata.duration_ms > 0 ||
          metadata.cost_estimate > 0) && (
          <details className="text-xs text-text-tertiary">
            <summary className="cursor-pointer select-none hover:text-text-secondary">
              Details
            </summary>
            <div className="mt-1 flex flex-wrap gap-4">
              {metadata.model && <span>Model: {metadata.model}</span>}
              {metadata.duration_ms > 0 && (
                <span>{(metadata.duration_ms / 1000).toFixed(1)}s</span>
              )}
              {metadata.cost_estimate > 0 && (
                <span>${metadata.cost_estimate.toFixed(4)}</span>
              )}
              {metadata.input_tokens + metadata.output_tokens > 0 && (
                <span>
                  {metadata.input_tokens + metadata.output_tokens} tokens
                </span>
              )}
            </div>
          </details>
        )}
    </div>
  );
}
