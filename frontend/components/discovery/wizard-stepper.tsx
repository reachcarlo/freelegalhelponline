"use client";

interface StepInfo {
  label: string;
}

interface WizardStepperProps {
  steps: StepInfo[];
  currentStep: number;
}

export default function WizardStepper({ steps, currentStep }: WizardStepperProps) {
  return (
    <nav aria-label="Wizard progress" className="w-full">
      {/* Mobile: compact text */}
      <p className="text-sm text-text-secondary sm:hidden mb-2">
        Step {currentStep + 1} of {steps.length}
        {steps[currentStep] && (
          <span className="text-text-primary font-medium">
            {" — "}
            {steps[currentStep].label}
          </span>
        )}
      </p>

      {/* Progress bar (all sizes) */}
      <div className="flex items-center gap-1">
        {steps.map((step, i) => {
          const isComplete = i < currentStep;
          const isCurrent = i === currentStep;

          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              {/* Bar segment */}
              <div
                className={`h-1 w-full rounded-full transition-colors ${
                  isComplete
                    ? "bg-accent"
                    : isCurrent
                      ? "bg-accent/60"
                      : "bg-border"
                }`}
              />

              {/* Label (desktop only) */}
              <span
                className={`hidden sm:block text-xs truncate max-w-full px-1 text-center ${
                  isComplete || isCurrent
                    ? "text-text-primary font-medium"
                    : "text-text-tertiary"
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </nav>
  );
}
