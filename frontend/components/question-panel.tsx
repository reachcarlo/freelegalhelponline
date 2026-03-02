"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { askQuestion } from "@/lib/api";
import { useConsent } from "@/lib/consent-context";
import { useMode } from "@/lib/mode-context";
import { useConversation } from "@/lib/use-conversation";
import { topics } from "@/lib/topics";
import ConsentModal from "./consent-modal";
import ConversationEnded from "./conversation-ended";
import ConversationTurnView from "./conversation-turn";
import ModeToggle from "./mode-toggle";
import QuestionInput from "./question-input";
import TurnProgress from "./turn-progress";

export default function QuestionPanel() {
  const { mode, setMode } = useMode();
  const { hasConsentedForMode, grantConsentForMode } = useConsent();

  const conversation = useConversation(mode);
  const [query, setQuery] = useState("");
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Scroll refs
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Track whether user is near the bottom of scroll container
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    isNearBottomRef.current = distanceFromBottom < 150;
    setShowScrollButton(distanceFromBottom > 300);
  }, []);

  // Scroll to bottom when streaming starts or a turn completes
  useEffect(() => {
    if (conversation.turns.length > 0 || conversation.isStreaming) {
      requestAnimationFrame(() => {
        const container = scrollContainerRef.current;
        if (container) {
          container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
          isNearBottomRef.current = true;
        }
      });
    }
  }, [conversation.turns.length, conversation.isStreaming]);

  // Throttled smooth scroll during streaming — 200ms interval avoids jitter
  useEffect(() => {
    if (!conversation.isStreaming) return;
    const timer = setInterval(() => {
      const container = scrollContainerRef.current;
      if (container && isNearBottomRef.current) {
        container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
      }
    }, 200);
    return () => clearInterval(timer);
  }, [conversation.isStreaming]);

  // Reset conversation when mode changes
  const prevModeRef = useRef(mode);
  useEffect(() => {
    if (prevModeRef.current !== mode) {
      prevModeRef.current = mode;
      conversation.startNewConversation();
      setQuery("");
    }
  }, [mode, conversation.startNewConversation]);

  const submitQuery = useCallback(
    (q: string) => {
      conversation.abortRef.current?.abort();
      conversation.beginTurn(q);
      setQuery("");

      const controller = askQuestion(
        q,
        mode,
        {
          onSources: conversation.onSources,
          onToken: conversation.onToken,
          onDone: conversation.onDone,
          onError: conversation.onError,
        },
        {
          session_id: conversation.sessionId,
          conversation_history: conversation.buildConversationHistory(),
          turn_number: conversation.currentTurn,
        }
      );

      conversation.abortRef.current = controller;
    },
    [mode, conversation]
  );

  const handleSubmit = useCallback(
    (q: string) => {
      if (!hasConsentedForMode(mode)) {
        setPendingQuery(q);
        setShowConsentModal(true);
        return;
      }
      submitQuery(q);
    },
    [hasConsentedForMode, mode, submitQuery]
  );

  const handleConsent = useCallback(() => {
    grantConsentForMode(mode);
    setShowConsentModal(false);
    if (pendingQuery) {
      submitQuery(pendingQuery);
      setPendingQuery(null);
    }
  }, [grantConsentForMode, mode, pendingQuery, submitQuery]);

  const handleConsentCancel = useCallback(() => {
    setShowConsentModal(false);
    setPendingQuery(null);
  }, []);

  const handleModeChange = useCallback(
    (newMode: "consumer" | "attorney") => {
      setMode(newMode);
    },
    [setMode]
  );

  const handleNewChat = useCallback(() => {
    conversation.startNewConversation();
    setQuery("");
  }, [conversation.startNewConversation]);

  const handleStop = useCallback(() => {
    conversation.stopStreaming();
  }, [conversation.stopStreaming]);

  const handleRetry = useCallback(() => {
    if (conversation.streamingQuery) {
      conversation.clearError();
      submitQuery(conversation.streamingQuery);
    }
  }, [conversation, submitQuery]);

  const scrollToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, []);

  const hasTurns = conversation.turns.length > 0 || conversation.isStreaming;

  return (
    <>
      {showConsentModal && (
        <ConsentModal
          mode={mode}
          onConsent={handleConsent}
          onCancel={handleConsentCancel}
        />
      )}

      <div className="flex flex-1 flex-col min-h-0">
        {!hasTurns ? (
          /* ── Idle: Centered Hero ── */
          <div className="flex flex-1 flex-col items-center overflow-y-auto px-4 sm:px-6">
            <div className="my-auto w-full max-w-3xl py-8">
              <h1 className="text-center text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
                Find Legal Help
              </h1>
              <p className="mt-3 text-center text-lg text-text-secondary">
                California Employment Rights — Answered by AI
              </p>
              <p className="mt-2 text-center text-sm text-text-tertiary">
                Ask questions about wages, discrimination, retaliation, leave,
                unemployment insurance, and other California workplace
                protections.
              </p>
              <div className="mt-3 flex items-center justify-center gap-4">
                <ModeToggle
                  mode={mode}
                  onChange={handleModeChange}
                  disabled={conversation.isStreaming}
                />
              </div>
              <p className="mt-2 text-center text-sm text-text-tertiary">
                {mode === "consumer"
                  ? "Plain-language answers focused on your rights and next steps."
                  : "Statutory analysis with code citations for legal research."}
              </p>

              {/* Error banner (first-query failures) */}
              {conversation.error && !conversation.isAtLimit && (
                <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
                  <span>{conversation.error}</span>
                  <button
                    onClick={handleRetry}
                    className="shrink-0 rounded-md border border-error-border px-3 py-1.5 text-xs font-medium
                               transition-colors hover:bg-error-border/20
                               focus:outline-none focus:ring-2 focus:ring-error-border/40"
                  >
                    Try Again
                  </button>
                </div>
              )}

              {/* Input */}
              <div className="mt-6">
                <QuestionInput
                  value={query}
                  onChange={setQuery}
                  onSubmit={handleSubmit}
                  onStop={handleStop}
                  isStreaming={conversation.isStreaming}
                  placeholder={
                    mode === "consumer"
                      ? "What's happening at your workplace?"
                      : "Search California employment statutes..."
                  }
                  maxHeight={mode === "attorney" ? 320 : 200}
                />
              </div>

              {/* Browse by Topic */}
              <section className="mt-8">
                <h2 className="text-center text-lg font-semibold text-text-primary">
                  Browse by Topic
                </h2>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {topics.map((topic) => (
                    <Link
                      key={topic.slug}
                      href={`/topics/${topic.slug}`}
                      className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
                    >
                      {topic.shortTitle}
                    </Link>
                  ))}
                </div>
              </section>

              {/* Free Tools */}
              <section className="mt-8">
                <h2 className="text-center text-lg font-semibold text-text-primary">
                  Free Legal Tools
                </h2>
                <p className="mt-2 text-center text-sm text-text-tertiary">
                  Interactive calculators and guides — no AI needed.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <Link
                    href="/tools/guided-intake"
                    className="rounded-full border border-accent bg-accent-surface px-4 py-2 text-sm text-accent transition-colors hover:bg-accent hover:text-white"
                  >
                    Get Your Rights Summary
                  </Link>
                  <Link
                    href="/tools/deadline-calculator"
                    className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
                  >
                    Deadline Calculator
                  </Link>
                  <Link
                    href="/tools/agency-routing"
                    className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
                  >
                    Agency Routing
                  </Link>
                  <Link
                    href="/tools/unpaid-wages-calculator"
                    className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
                  >
                    Unpaid Wages Calculator
                  </Link>
                  <Link
                    href="/tools/incident-docs"
                    className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
                  >
                    Incident Docs
                  </Link>
                </div>
                <div className="mt-3 text-center">
                  <Link
                    href="/tools"
                    className="text-sm text-accent hover:text-accent-hover underline"
                  >
                    View all tools
                  </Link>
                </div>
              </section>
            </div>
          </div>
        ) : (
          /* ── Conversation: 3-Zone Layout ── */
          <>
            {/* Zone 1: Compact header */}
            <div className="shrink-0 px-4 pt-4 pb-2 sm:px-6">
              <div className="mx-auto max-w-3xl">
                <h1 className="text-center text-lg font-bold tracking-tight text-text-primary">
                  Find Legal Help
                </h1>
                <div className="mt-3 flex items-center justify-center gap-4">
                  <ModeToggle
                    mode={mode}
                    onChange={handleModeChange}
                    disabled={conversation.isStreaming}
                  />
                  <button
                    onClick={handleNewChat}
                    disabled={conversation.isStreaming}
                    className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium
                               text-text-secondary transition-colors hover:bg-surface-raised
                               focus:outline-none focus:ring-2 focus:ring-accent/20
                               disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    New Chat
                  </button>
                  <Link
                    href="/tools"
                    className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium
                               text-text-secondary transition-colors hover:bg-surface-raised
                               focus:outline-none focus:ring-2 focus:ring-accent/20"
                  >
                    Tools
                  </Link>
                </div>
                <p className="mt-2 text-center text-sm text-text-tertiary">
                  {mode === "consumer"
                    ? "Plain-language answers focused on your rights and next steps."
                    : "Statutory analysis with code citations for legal research."}
                </p>
              </div>
            </div>

            {/* Zone 2: Scrollable message area */}
            <div
              ref={scrollContainerRef}
              onScroll={handleScroll}
              className="relative flex-1 overflow-y-auto"
            >
              <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
                <div className="flex flex-col gap-8">
                  {/* Turn progress */}
                  <div className="flex justify-center">
                    <TurnProgress
                      currentTurn={conversation.currentTurn}
                      maxTurns={conversation.maxTurns}
                      isStreaming={conversation.isStreaming}
                    />
                  </div>

                  {/* Error message with retry */}
                  {conversation.error && !conversation.isAtLimit && (
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
                      <span>{conversation.error}</span>
                      <button
                        onClick={handleRetry}
                        className="shrink-0 rounded-md border border-error-border px-3 py-1.5 text-xs font-medium
                                   transition-colors hover:bg-error-border/20
                                   focus:outline-none focus:ring-2 focus:ring-error-border/40"
                      >
                        Try Again
                      </button>
                    </div>
                  )}

                  {/* Conversation thread — completed turns */}
                  {conversation.turns.map((turn, i) => (
                    <ConversationTurnView
                      key={i}
                      query={turn.query}
                      answer={turn.answer}
                      sources={turn.sources}
                      metadata={turn.metadata}
                      isStreaming={false}
                      isLatest={
                        i === conversation.turns.length - 1 &&
                        !conversation.isStreaming
                      }
                      mode={mode}
                    />
                  ))}

                  {/* Currently streaming turn */}
                  {conversation.isStreaming && (
                    <ConversationTurnView
                      query={conversation.streamingQuery}
                      answer={conversation.streamingAnswer}
                      sources={conversation.streamingSources}
                      metadata={null}
                      isStreaming={true}
                      isLatest={true}
                      mode={mode}
                    />
                  )}

                  {/* Conversation ended banner */}
                  {conversation.isAtLimit && (
                    <ConversationEnded onStartNew={handleNewChat} />
                  )}

                </div>
              </div>

              {/* Scroll-to-bottom FAB */}
              {showScrollButton && (
                <button
                  onClick={scrollToBottom}
                  className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-border
                             bg-surface p-2.5 shadow-lg transition-all hover:bg-surface-raised
                             focus:outline-none focus:ring-2 focus:ring-accent/20"
                  aria-label="Scroll to bottom"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    className="text-text-secondary"
                  >
                    <path
                      d="M8 3v10m0 0l-4-4m4 4l4-4"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              )}
            </div>

            {/* Zone 3: Input area */}
            {!conversation.isAtLimit && (
              <div className="shrink-0 border-t border-border bg-background px-4 pb-[env(safe-area-inset-bottom,0px)] sm:px-6">
                <div className="mx-auto max-w-3xl py-3">
                  <QuestionInput
                    value={query}
                    onChange={setQuery}
                    onSubmit={handleSubmit}
                    onStop={handleStop}
                    isStreaming={conversation.isStreaming}
                    placeholder={
                      mode === "consumer"
                        ? "Ask a follow-up..."
                        : "Follow-up or new question..."
                    }
                    maxHeight={mode === "attorney" ? 320 : 200}
                  />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
