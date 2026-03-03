"use client";

import { useCallback, useState } from "react";
import {
  downloadBlob,
  generateDocument,
  TOOL_SHORT_LABELS,
  type GenerateOptions,
} from "@/lib/discovery-api";

interface DownloadButtonProps {
  options: GenerateOptions;
  disabled?: boolean;
}

export default function DownloadButton({
  options,
  disabled = false,
}: DownloadButtonProps) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setSuccess(false);

    try {
      const { blob, filename } = await generateDocument(options);
      downloadBlob(blob, filename);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }, [options]);

  const label = TOOL_SHORT_LABELS[options.tool_type] || options.tool_type;
  const isDocx = !options.tool_type.includes("frogs");

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleGenerate}
        disabled={disabled || generating}
        className={`min-h-[44px] w-full rounded-lg px-5 py-3 text-sm font-semibold transition-colors ${
          disabled || generating
            ? "cursor-not-allowed bg-accent/30 text-text-tertiary"
            : success
              ? "bg-verified-bg text-verified-text border border-verified-border"
              : "bg-accent text-white hover:bg-accent-hover"
        }`}
      >
        {generating ? (
          <span className="flex items-center justify-center gap-2">
            <svg
              className="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Generating {label}…
          </span>
        ) : success ? (
          "Downloaded!"
        ) : (
          `Generate ${label} (${isDocx ? ".docx" : ".pdf"})`
        )}
      </button>

      {error && (
        <p className="rounded-lg border border-error-border bg-error-bg px-3 py-2 text-xs text-error-text">
          {error}
        </p>
      )}
    </div>
  );
}
