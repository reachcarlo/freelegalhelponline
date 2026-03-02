"use client";

import { useEffect, useRef, useState } from "react";

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (query: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
  maxHeight?: number;
}

export default function QuestionInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = "Ask a question about California employment law...",
  maxHeight = 200,
}: QuestionInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // Auto-grow textarea based on content, capped at maxHeight
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, maxHeight) + "px";
  }, [value, maxHeight]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !disabled && !isStreaming) {
      onSubmit(trimmed);
      textareaRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed && !disabled && !isStreaming) {
        onSubmit(trimmed);
        textareaRef.current?.focus();
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full" aria-label="Ask a question">
      <div className="flex items-end gap-3">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          className="peer flex-1 resize-none rounded-lg border border-border bg-input-bg px-4 py-3 text-base
                     text-text-primary placeholder-text-tertiary shadow-sm transition-colors
                     focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20
                     disabled:cursor-not-allowed disabled:opacity-60"
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg
                       border-2 border-accent bg-transparent text-accent shadow-sm
                       transition-colors hover:bg-accent/10
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
                       disabled:cursor-not-allowed disabled:bg-text-tertiary disabled:opacity-40"
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 13V3m0 0l-4 4m4-4l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
      <p
        className={`mt-1 text-xs text-text-tertiary transition-opacity duration-150 ${
          isFocused && value.length > 0 ? "opacity-100" : "opacity-0"
        }`}
        aria-hidden="true"
      >
        Shift + Enter for new line
      </p>
    </form>
  );
}
