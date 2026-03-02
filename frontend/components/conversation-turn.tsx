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
    <div
      className="flex flex-col gap-4 animate-fade-in"
      style={{ overflowAnchor: "none" }}
    >
      {/* User query bubble */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-accent/10 px-4 py-3 text-sm text-text-primary">
          {query}
        </div>
      </div>

      {/* Sources */}
      <SourceList sources={sources} />

      {/* AI answer with copy button */}
      {(answer || isStreaming) && (
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
      )}

      {/* Per-answer disclaimer — shown after answer completes */}
      {answer && !isStreaming && (
        <p className="text-[11px] leading-tight text-text-tertiary/70">
          {mode === "attorney"
            ? "This analysis is based on statutory text in our database and should be independently verified against current authority. It does not constitute legal advice."
            : "This information is for educational purposes only and is not legal advice. For guidance about your specific situation, consult a licensed California employment attorney."}
        </p>
      )}

      {/* Citation verification badges — attorney mode only */}
      {answer &&
        !isStreaming &&
        mode === "attorney" &&
        metadata?.citation_verifications &&
        metadata.citation_verifications.length > 0 && (
          <CitationBadges verifications={metadata.citation_verifications} />
        )}

      {/* Metadata and feedback — only on the latest completed turn */}
      {isLatest && metadata && !isStreaming && (
        <>
          <div className="flex flex-wrap gap-4 text-xs text-text-tertiary">
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
          {metadata.query_id && <FeedbackButtons queryId={metadata.query_id} />}
        </>
      )}
    </div>
  );
}
