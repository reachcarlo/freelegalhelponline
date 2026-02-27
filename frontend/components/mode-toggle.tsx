"use client";

interface ModeToggleProps {
  mode: "consumer" | "attorney";
  onChange: (mode: "consumer" | "attorney") => void;
  disabled?: boolean;
}

export default function ModeToggle({
  mode,
  onChange,
  disabled = false,
}: ModeToggleProps) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-toggle-bg p-1">
      <button
        type="button"
        onClick={() => onChange("consumer")}
        disabled={disabled}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          mode === "consumer"
            ? "bg-toggle-active-bg text-text-primary shadow-sm"
            : "text-text-tertiary hover:text-text-secondary"
        } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
      >
        Employee
      </button>
      <button
        type="button"
        onClick={() => onChange("attorney")}
        disabled={disabled}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          mode === "attorney"
            ? "bg-toggle-active-bg text-text-primary shadow-sm"
            : "text-text-tertiary hover:text-text-secondary"
        } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
      >
        Legal Professional
      </button>
    </div>
  );
}
