"use client";

import { useEffect, useState } from "react";
import Markdown from "react-markdown";

interface AnswerDisplayProps {
  text: string;
  isStreaming: boolean;
  mode?: "consumer" | "attorney";
}

const SLOW_THRESHOLD_MS = 15_000;

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
    const timer = setTimeout(() => setShowSlowMessage(true), SLOW_THRESHOLD_MS);
    return () => clearTimeout(timer);
  }, [isStreaming, text]);

  if (!text && !isStreaming) return null;

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-6">
      {text && (
        <div className="prose max-w-none">
          <Markdown>{text}</Markdown>
        </div>
      )}
      {isStreaming && !text && showSlowMessage && mode === "attorney" && (
        <p className="animate-pulse text-sm text-text-tertiary">
          Generating detailed statutory analysis...
        </p>
      )}
      {isStreaming && !text && !showSlowMessage && (
        <span className="inline-block animate-pulse text-sm text-text-tertiary">
          Generating...
        </span>
      )}
      {isStreaming && text && (
        <span className="mt-2 inline-block animate-pulse text-sm text-text-tertiary">
          Generating...
        </span>
      )}
    </div>
  );
}
