"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Link from "next/link";
import {
  getQuestions,
  evaluateIntake,
  type IntakeQuestion as IntakeQuestionInfo,
  type IntakeResult as IntakeResponse,
} from "@/lib/calculators/intake";
import { streamIntakeSummary, type SourceInfo } from "@/lib/api";
import AnswerDisplay from "@/components/answer-display";
import SourceList from "@/components/source-list";

function confidenceBadge(confidence: string) {
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
  const [fetchLoading, setFetchLoading] = useState(true);
  const [error, setError] = useState("");
  const [slideDirection, setSlideDirection] = useState<"right" | "left">("right");
  // P1: Auto-advance flag — set true when a single-select option is picked
  const [pendingAutoAdvance, setPendingAutoAdvance] = useState(false);
  const submitRef = useRef<() => void>(() => {});

  // Rights summary streaming state
  const [summaryText, setSummaryText] = useState("");
  const [summarySources, setSummarySources] = useState<SourceInfo[]>([]);
  const [summaryStreaming, setSummaryStreaming] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const summaryAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setQuestions(getQuestions());
    setFetchLoading(false);
  }, []);

  // Auto-trigger rights summary stream after intake results load
  useEffect(() => {
    if (!result || result.identified_issues.length === 0) return;
    const allAnswers = Object.values(answers).flat();
    setSummaryStreaming(true);
    setSummaryText("");
    setSummarySources([]);
    setSummaryError("");

    const controller = streamIntakeSummary(allAnswers, {
      onSources: (s) => setSummarySources(s),
      onToken: (t) => setSummaryText((prev) => prev + t),
      onDone: () => setSummaryStreaming(false),
      onError: (e) => {
        setSummaryError(e);
        setSummaryStreaming(false);
      },
    });
    summaryAbortRef.current = controller;
    return () => controller.abort();
  }, [result]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Keep submitRef current so the auto-advance effect can call it
  submitRef.current = () => {
    handleSubmit();
  };

  // P1: Auto-advance effect — fires after answer state has settled
  useEffect(() => {
    if (!pendingAutoAdvance) return;
    const timer = setTimeout(() => {
      setPendingAutoAdvance(false);
      if (isLastStep) {
        submitRef.current();
      } else {
        setSlideDirection("right");
        setCurrentStep((s) => s + 1);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [pendingAutoAdvance, isLastStep]);

  const handleSelect = useCallback(
    (questionId: string, key: string, allowMultiple: boolean) => {
      setPendingAutoAdvance(false); // cancel any pending

      setAnswers((prev) => {
        const current = prev[questionId] ?? [];
        if (allowMultiple) {
          const next = current.includes(key)
            ? current.filter((k) => k !== key)
            : [...current, key];
          return { ...prev, [questionId]: next };
        }
        return { ...prev, [questionId]: [key] };
      });

      // P1: Queue auto-advance for single-select only
      if (!allowMultiple) {
        setPendingAutoAdvance(true);
      }
    },
    []
  );

  const handleNext = useCallback(() => {
    setPendingAutoAdvance(false);
    if (isLastStep) {
      handleSubmit();
    } else {
      setSlideDirection("right");
      setCurrentStep((s) => s + 1);
    }
  }, [isLastStep]);

  const handleBack = useCallback(() => {
    setPendingAutoAdvance(false);
    if (currentStep > 0) {
      setSlideDirection("left");
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

  function handleSubmit() {
    setError("");

    try {
      const allAnswers = Object.values(answers).flat();
      const data = evaluateIntake(allAnswers);
      setResult(data);
      // P4: Scroll to top on results
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  function handleStartOver() {
    summaryAbortRef.current?.abort();
    setAnswers({});
    setCurrentStep(0);
    setResult(null);
    setError("");
    setSlideDirection("right");
    setPendingAutoAdvance(false);
    setSummaryText("");
    setSummarySources([]);
    setSummaryStreaming(false);
    setSummaryError("");
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

        {/* P6: Stronger empty-results CTA */}
        {result.identified_issues.length === 0 && (
          <div className="rounded-lg border border-border bg-surface-raised p-5 space-y-4">
            <p className="text-sm text-text-secondary">
              We could not match your answers to a specific employment law issue.
              Your situation may be unique — try describing it in your own words.
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <Link
                href="/"
                className="min-h-[44px] inline-flex items-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
              >
                Describe Your Situation to AI
              </Link>
              <button
                onClick={handleStartOver}
                className="min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-raised"
              >
                Try Again
              </button>
            </div>
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
                  {/* P5: Reworded pre-selected label */}
                  {Object.keys(tool.prefill_params).length > 0 && (
                    <p className="mt-1 text-xs text-accent italic">
                      {Object.values(tool.prefill_params)
                        .map((v) =>
                          v
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (c) => c.toUpperCase())
                        )
                        .join(", ")}{" "}
                      will be pre-selected for you
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </div>
        ))}

        {/* Rights summary section */}
        {result.identified_issues.length > 0 && (
          <div className="rounded-lg border border-border bg-surface-raised p-5 space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                Your Rights Summary
              </h2>
              <p className="mt-1 text-sm text-text-tertiary">
                Personalized overview based on your answers
              </p>
            </div>

            {summaryStreaming && !summaryText && (
              <div className="flex items-center gap-2 text-sm text-text-tertiary">
                <span className="inline-block h-4 w-4 animate-pulse rounded-full bg-accent/40" />
                Generating your personalized rights summary...
              </div>
            )}

            {summaryText && (
              <AnswerDisplay
                text={summaryText}
                isStreaming={summaryStreaming}
                mode="consumer"
              />
            )}

            {!summaryStreaming && summarySources.length > 0 && (
              <SourceList sources={summarySources} />
            )}

            {summaryError && (
              <div className="rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text flex items-center justify-between gap-4">
                <span>Failed to generate summary. {summaryError}</span>
                <button
                  onClick={() => {
                    // Re-trigger by toggling result
                    const r = result;
                    setResult(null);
                    setTimeout(() => setResult(r), 0);
                  }}
                  className="shrink-0 rounded-lg border border-error-border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-error-bg"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        {result.identified_issues.length > 0 && (
          <div className="flex items-center gap-4 flex-wrap">
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
        )}
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
      {/* P7: Progress — fraction only, no percentage */}
      <div>
        <p className="text-xs text-text-tertiary mb-2">
          Question {currentStep + 1} of {visibleQuestions.length}
        </p>
        {/* P8: ARIA progressbar */}
        <div
          role="progressbar"
          aria-valuenow={currentStep + 1}
          aria-valuemax={visibleQuestions.length}
          aria-label="Questionnaire progress"
          className="h-2 w-full rounded-full bg-badge-bg overflow-hidden"
        >
          <div
            className="h-full rounded-full bg-accent transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* P2: Animated question transition via key remount */}
      <div
        key={currentQuestion.question_id}
        className={
          slideDirection === "right"
            ? "animate-slide-in-right"
            : "animate-slide-in-left"
        }
      >
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

        {/* P8: ARIA role group for options */}
        <div
          className="mt-6 space-y-2"
          role={currentQuestion.allow_multiple ? "group" : "radiogroup"}
          aria-label={currentQuestion.question_text}
        >
          {currentQuestion.options.map((opt) => {
            const isSelected = selectedKeys.includes(opt.key);
            return (
              <button
                key={opt.key}
                type="button"
                role={currentQuestion.allow_multiple ? "checkbox" : "radio"}
                aria-checked={isSelected}
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
                  <div className="mt-0.5 flex-shrink-0" aria-hidden="true">
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
          disabled={!hasAnswer}
          className="min-h-[44px] rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLastStep ? "See Results" : "Next"}
        </button>
      </div>
    </div>
  );
}
