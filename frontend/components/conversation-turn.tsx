"use client";

import type { AskMetadata, SourceInfo } from "@/lib/api";
import AnswerDisplay from "./answer-display";
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
  return (
    <div className="flex flex-col gap-4">
      {/* User query bubble */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-accent/10 px-4 py-3 text-sm text-text-primary">
          {query}
        </div>
      </div>

      {/* Sources */}
      <SourceList sources={sources} />

      {/* AI answer */}
      <AnswerDisplay text={answer} isStreaming={isStreaming} mode={mode} />

      {/* Per-answer disclaimer — shown after answer completes */}
      {answer && !isStreaming && (
        <p className="text-[11px] leading-tight text-text-tertiary/70">
          {mode === "attorney"
            ? "This analysis is based on statutory text in our database and should be independently verified against current authority. It does not constitute legal advice."
            : "This information is for educational purposes only and is not legal advice. For guidance about your specific situation, consult a licensed California employment attorney."}
        </p>
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
