"use client";

interface WizardNavigationProps {
  currentStep: number;
  totalSteps: number;
  onBack: () => void;
  onNext: () => void;
  onGenerate?: () => void;
  nextDisabled?: boolean;
  generateDisabled?: boolean;
  generating?: boolean;
  nextLabel?: string;
}

export default function WizardNavigation({
  currentStep,
  totalSteps,
  onBack,
  onNext,
  onGenerate,
  nextDisabled = false,
  generateDisabled = false,
  generating = false,
  nextLabel,
}: WizardNavigationProps) {
  const isFirst = currentStep === 0;
  const isLast = currentStep === totalSteps - 1;

  return (
    <div className="flex items-center justify-between border-t border-border bg-surface px-4 py-3 sm:px-6">
      {/* Back */}
      <button
        type="button"
        onClick={onBack}
        disabled={isFirst}
        className={`min-h-[44px] min-w-[44px] rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
          isFirst
            ? "cursor-not-allowed text-text-tertiary"
            : "text-text-secondary hover:bg-accent-surface hover:text-accent"
        }`}
      >
        Back
      </button>

      {/* Step indicator (center) */}
      <span className="text-xs text-text-tertiary">
        {currentStep + 1} / {totalSteps}
      </span>

      {/* Next or Generate */}
      {isLast && onGenerate ? (
        <button
          type="button"
          onClick={onGenerate}
          disabled={generateDisabled || generating}
          className={`min-h-[44px] min-w-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors ${
            generateDisabled || generating
              ? "cursor-not-allowed bg-accent/30 text-text-tertiary"
              : "bg-accent text-white hover:bg-accent-hover"
          }`}
        >
          {generating ? (
            <span className="flex items-center gap-2">
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
              Generating…
            </span>
          ) : (
            "Generate Document"
          )}
        </button>
      ) : (
        <button
          type="button"
          onClick={onNext}
          disabled={nextDisabled}
          className={`min-h-[44px] min-w-[44px] rounded-lg px-5 py-2 text-sm font-semibold transition-colors ${
            nextDisabled
              ? "cursor-not-allowed bg-accent/30 text-text-tertiary"
              : "bg-accent text-white hover:bg-accent-hover"
          }`}
        >
          {nextLabel || "Next"}
        </button>
      )}
    </div>
  );
}
