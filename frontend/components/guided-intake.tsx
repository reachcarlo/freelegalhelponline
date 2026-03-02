"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  getIntakeQuestions,
  evaluateIntake,
  type IntakeQuestionInfo,
  type IntakeResponse,
} from "@/lib/api";

function confidenceBadge(confidence: "high" | "medium") {
  if (confidence === "high") {
    return (
      <span className="inline-flex items-center rounded-full bg-accent-surface border border-accent px-2.5 py-0.5 text-xs font-medium text-accent">
        High confidence
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-warning-bg border border-warning-border px-2.5 py-0.5 text-xs font-medium text-warning-text">
      Possible match
    </span>
  );
}

export default function GuidedIntake() {
  const [questions, setQuestions] = useState<IntakeQuestionInfo[]>([]);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState<IntakeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getIntakeQuestions()
      .then((data) => {
        setQuestions(data.questions);
        setFetchLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load questions.");
        setFetchLoading(false);
      });
  }, []);

  // Compute visible questions based on current answers
  const visibleQuestions = useMemo(() => {
    const allAnswers = new Set(Object.values(answers).flat());
    return questions.filter((q) => {
      if (!q.show_if) return true;
      return q.show_if.some((key) => allAnswers.has(key));
    });
  }, [questions, answers]);

  const currentQuestion = visibleQuestions[currentStep] ?? null;
  const isLastStep = currentStep === visibleQuestions.length - 1;

  const handleSelect = useCallback(
    (questionId: string, key: string, allowMultiple: boolean) => {
      setAnswers((prev) => {
        const current = prev[questionId] ?? [];
        if (allowMultiple) {
          // Toggle
          const next = current.includes(key)
            ? current.filter((k) => k !== key)
            : [...current, key];
          return { ...prev, [questionId]: next };
        }
        return { ...prev, [questionId]: [key] };
      });
    },
    []
  );

  const handleNext = useCallback(() => {
    if (isLastStep) {
      handleSubmit();
    } else {
      setCurrentStep((s) => Math.min(s + 1, visibleQuestions.length - 1));
    }
  }, [isLastStep, visibleQuestions.length]);

  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
      // Clear answers for questions that may become hidden
      setAnswers((prev) => {
        const allAnswersSet = new Set(Object.values(prev).flat());
        const nowVisible = new Set(
          questions
            .filter((q) => !q.show_if || q.show_if.some((k) => allAnswersSet.has(k)))
            .map((q) => q.question_id)
        );
        const cleaned: Record<string, string[]> = {};
        for (const [qId, vals] of Object.entries(prev)) {
          if (nowVisible.has(qId)) {
            cleaned[qId] = vals;
          }
        }
        return cleaned;
      });
    }
  }, [currentStep, questions]);

  async function handleSubmit() {
    setLoading(true);
    setError("");

    try {
      const allAnswers = Object.values(answers).flat();
      const data = await evaluateIntake(allAnswers);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleStartOver() {
    setAnswers({});
    setCurrentStep(0);
    setResult(null);
    setError("");
  }

  // Loading state
  if (fetchLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-text-tertiary">Loading questionnaire...</p>
      </div>
    );
  }

  // Results phase
  if (result) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-border bg-surface-raised p-5">
          <h2 className="text-lg font-semibold text-text-primary">Your Results</h2>
          <p className="mt-2 text-sm text-text-secondary">{result.summary}</p>
        </div>

        {result.is_government_employee && (
          <div className="rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
            <strong>Government Employee Note:</strong> As a government employee,
            you may have additional filing requirements, including exhausting
            internal administrative remedies before filing with external agencies.
          </div>
        )}

        {result.identified_issues.length === 0 && (
          <div className="rounded-lg border border-border bg-surface-raised p-5 text-sm text-text-secondary">
            We could not identify a specific employment law issue from your
            answers. Consider speaking with a California employment attorney for
            personalized guidance, or try the{" "}
            <Link href="/" className="text-accent hover:text-accent-hover underline">
              AI chat
            </Link>{" "}
            for more help.
          </div>
        )}

        {result.identified_issues.map((issue) => (
          <div
            key={issue.issue_type}
            className="rounded-lg border border-border bg-surface-raised p-5"
          >
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <h3 className="font-semibold text-text-primary">{issue.issue_label}</h3>
              <div className="flex items-center gap-2 flex-wrap">
                {confidenceBadge(issue.confidence)}
                {issue.has_deadline_urgency && (
                  <span className="inline-flex items-center rounded-full bg-error-bg border border-error-border px-2.5 py-0.5 text-xs font-medium text-error-text">
                    Filing deadlines apply
                  </span>
                )}
              </div>
            </div>
            <p className="mt-2 text-sm text-text-secondary">{issue.description}</p>

            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
                Recommended tools
              </p>
              {issue.tools.map((tool) => (
                <Link
                  key={tool.tool_name}
                  href={tool.tool_path}
                  className="block rounded-lg border border-border p-3 transition-colors hover:border-border-hover hover:bg-accent-surface"
                >
                  <p className="font-medium text-text-primary text-sm">
                    {tool.tool_label}
                  </p>
                  <p className="mt-1 text-xs text-text-secondary">
                    {tool.description}
                  </p>
                  {Object.keys(tool.prefill_params).length > 0 && (
                    <p className="mt-1 text-xs text-accent">
                      Pre-selected:{" "}
                      {Object.values(tool.prefill_params)
                        .map((v) => v.replace(/_/g, " "))
                        .join(", ")}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </div>
        ))}

        <div className="flex items-center gap-4">
          <button
            onClick={handleStartOver}
            className="min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-raised"
          >
            Start Over
          </button>
          <Link
            href="/"
            className="min-h-[44px] inline-flex items-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
          >
            Ask AI for Personalized Guidance
          </Link>
        </div>
      </div>
    );
  }

  // Questionnaire phase
  if (!currentQuestion) {
    return null;
  }

  const selectedKeys = answers[currentQuestion.question_id] ?? [];
  const hasAnswer = selectedKeys.length > 0;
  const progress = visibleQuestions.length > 0
    ? ((currentStep + 1) / visibleQuestions.length) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between text-xs text-text-tertiary mb-2">
          <span>
            Question {currentStep + 1} of {visibleQuestions.length}
          </span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-badge-bg overflow-hidden">
          <div
            className="h-full rounded-full bg-accent transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Question */}
      <div>
        <h2 className="text-lg font-semibold text-text-primary">
          {currentQuestion.question_text}
        </h2>
        {currentQuestion.help_text && (
          <p className="mt-1 text-sm text-text-tertiary">
            {currentQuestion.help_text}
          </p>
        )}
      </div>

      {/* Options */}
      <div className="space-y-2">
        {currentQuestion.options.map((opt) => {
          const isSelected = selectedKeys.includes(opt.key);
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() =>
                handleSelect(
                  currentQuestion.question_id,
                  opt.key,
                  currentQuestion.allow_multiple
                )
              }
              className={`w-full min-h-[44px] text-left rounded-lg border p-3 transition-colors ${
                isSelected
                  ? "border-accent bg-accent-surface"
                  : "border-border bg-surface-raised hover:border-border-hover"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0">
                  {currentQuestion.allow_multiple ? (
                    <div
                      className={`h-5 w-5 rounded border-2 flex items-center justify-center ${
                        isSelected
                          ? "border-accent bg-accent"
                          : "border-border"
                      }`}
                    >
                      {isSelected && (
                        <svg
                          className="h-3 w-3 text-white"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={3}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      )}
                    </div>
                  ) : (
                    <div
                      className={`h-5 w-5 rounded-full border-2 flex items-center justify-center ${
                        isSelected
                          ? "border-accent"
                          : "border-border"
                      }`}
                    >
                      {isSelected && (
                        <div className="h-2.5 w-2.5 rounded-full bg-accent" />
                      )}
                    </div>
                  )}
                </div>
                <div>
                  <p className="font-medium text-text-primary text-sm">
                    {opt.label}
                  </p>
                  {opt.help_text && (
                    <p className="mt-0.5 text-xs text-text-tertiary">
                      {opt.help_text}
                    </p>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {error && (
        <div className="rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
          {error}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={handleBack}
          disabled={currentStep === 0}
          className="min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-raised disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Back
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={!hasAnswer || loading}
          className="min-h-[44px] rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading
            ? "Analyzing..."
            : isLastStep
            ? "See Results"
            : "Next"}
        </button>
      </div>
    </div>
  );
}
