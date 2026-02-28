"use client";

import { useEffect, useRef } from "react";

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (query: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export default function QuestionInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = "Ask a question about California employment law...",
}: QuestionInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea based on content, capped at 200px
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [value]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !disabled && !isStreaming) {
      onSubmit(trimmed);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed && !disabled && !isStreaming) {
        onSubmit(trimmed);
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 resize-none rounded-lg border border-border bg-input-bg px-4 py-3 text-base
                     text-text-primary placeholder-text-tertiary shadow-sm transition-colors
                     focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20
                     disabled:cursor-not-allowed disabled:opacity-60"
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg bg-accent
                       text-white shadow-sm transition-colors hover:bg-accent-hover
                       focus:outline-none focus:ring-2 focus:ring-accent/20"
            aria-label="Stop generating"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="1" y="1" width="12" height="12" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            type="submit"
            disabled={disabled || !value.trim()}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg bg-accent
                       text-white shadow-sm transition-colors hover:bg-accent-hover
                       focus:outline-none focus:ring-2 focus:ring-accent/20
                       disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 13V3m0 0l-4 4m4-4l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
    </form>
  );
}
