"use client";

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (query: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function QuestionInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Ask a question about California employment law...",
}: QuestionInputProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !disabled) {
      onSubmit(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 rounded-lg border border-border bg-input-bg px-4 py-3 text-base
                     text-text-primary placeholder-text-tertiary shadow-sm transition-colors
                     focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20
                     disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white shadow-sm
                     transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2
                     focus:ring-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabled ? "Thinking..." : "Ask"}
        </button>
      </div>
    </form>
  );
}
