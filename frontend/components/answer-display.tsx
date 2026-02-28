"use client";

import React, { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";

interface AnswerDisplayProps {
  text: string;
  isStreaming: boolean;
  mode?: "consumer" | "attorney";
}

const SLOW_THRESHOLD_MS = 15_000;

/** Memoized block for paragraphs that won't change during streaming */
const StableMarkdown = React.memo(function StableMarkdown({
  content,
}: {
  content: string;
}) {
  return (
    <div className="prose max-w-none">
      <Markdown>{content}</Markdown>
    </div>
  );
});

export default function AnswerDisplay({
  text,
  isStreaming,
  mode,
}: AnswerDisplayProps) {
  const [showSlowMessage, setShowSlowMessage] = useState(false);

  useEffect(() => {
    if (!isStreaming || text.length > 0) {
      setShowSlowMessage(false);
      return;
    }
    const timer = setTimeout(
      () => setShowSlowMessage(true),
      SLOW_THRESHOLD_MS
    );
    return () => clearTimeout(timer);
  }, [isStreaming, text]);

  // Split at last paragraph boundary for memoized rendering
  const { stableContent, activeContent } = useMemo(() => {
    if (!isStreaming || !text) return { stableContent: "", activeContent: text };
    const lastBreak = text.lastIndexOf("\n\n");
    if (lastBreak === -1) return { stableContent: "", activeContent: text };
    return {
      stableContent: text.slice(0, lastBreak),
      activeContent: text.slice(lastBreak),
    };
  }, [text, isStreaming]);

  if (!text && !isStreaming) return null;

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-6">
      {/* Typing dots — before first token */}
      {isStreaming && !text && !showSlowMessage && (
        <div className="flex items-center gap-1.5 py-2">
          <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
          <span className="typing-dot h-2 w-2 rounded-full bg-accent [animation-delay:150ms]" />
          <span className="typing-dot h-2 w-2 rounded-full bg-accent [animation-delay:300ms]" />
        </div>
      )}

      {/* Slow response — typing dots + contextual label */}
      {isStreaming && !text && showSlowMessage && (
        <div className="flex items-center gap-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent [animation-delay:150ms]" />
            <span className="typing-dot h-2 w-2 rounded-full bg-accent [animation-delay:300ms]" />
          </div>
          <span className="text-sm text-text-tertiary">
            {mode === "attorney"
              ? "Analyzing statutes..."
              : "Researching your question..."}
          </span>
        </div>
      )}

      {/* Memoized stable content (everything before last paragraph break) */}
      {stableContent && <StableMarkdown content={stableContent} />}

      {/* Active content (current paragraph being streamed) */}
      {activeContent && (
        <div className="prose max-w-none">
          <Markdown>{activeContent}</Markdown>
        </div>
      )}

      {/* Blinking cursor during streaming */}
      {isStreaming && text && (
        <span className="ml-0.5 inline-block h-5 w-0.5 animate-blink bg-accent align-text-bottom" />
      )}
    </div>
  );
}
