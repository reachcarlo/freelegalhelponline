"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { askQuestion } from "@/lib/api";
import { useConsent } from "@/lib/consent-context";
import { useMode } from "@/lib/mode-context";
import { useConversation } from "@/lib/use-conversation";
import ConsentModal from "./consent-modal";
import ConversationEnded from "./conversation-ended";
import ConversationTurnView from "./conversation-turn";
import LoadingBar from "./loading-bar";
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

  // Scroll to bottom when new content appears
  const threadEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.turns.length, conversation.streamingAnswer]);

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

  const hasTurns = conversation.turns.length > 0 || conversation.isStreaming;
  const inputPlaceholder = hasTurns
    ? "Ask a follow-up..."
    : "Ask a question about California employment law...";

  // The question input component — rendered in different positions based on state
  const questionInput = !conversation.isAtLimit ? (
    <QuestionInput
      value={query}
      onChange={setQuery}
      onSubmit={handleSubmit}
      disabled={conversation.isStreaming}
      placeholder={inputPlaceholder}
    />
  ) : null;

  return (
    <>
      {showConsentModal && (
        <ConsentModal
          mode={mode}
          onConsent={handleConsent}
          onCancel={handleConsentCancel}
        />
      )}

      <div className="flex flex-col gap-6">
        {/* Header: mode toggle + New Chat button */}
        <div className="flex items-center justify-center gap-4">
          <ModeToggle
            mode={mode}
            onChange={handleModeChange}
            disabled={conversation.isStreaming}
          />
          {hasTurns && (
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
          )}
        </div>

        {/* Mode description */}
        <p className="text-center text-sm text-text-tertiary">
          {mode === "consumer"
            ? "Plain-language answers focused on your rights and next steps."
            : "Statutory analysis with code citations for legal research."}
        </p>

        {/* Turn progress */}
        {hasTurns && (
          <div className="flex justify-center">
            <TurnProgress
              currentTurn={conversation.currentTurn}
              maxTurns={conversation.maxTurns}
              isStreaming={conversation.isStreaming}
            />
          </div>
        )}

        {/* Question input — at top only before conversation starts */}
        {!hasTurns && questionInput}

        {/* Error message */}
        {conversation.error && !conversation.isAtLimit && (
          <div className="rounded-lg border border-error-border bg-error-bg p-4 text-sm text-error-text">
            {conversation.error}
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
              i === conversation.turns.length - 1 && !conversation.isStreaming
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

        {/* Loading bar */}
        <LoadingBar active={conversation.isStreaming} />

        {/* Question input — at bottom once conversation has started */}
        {hasTurns && questionInput}

        {/* Conversation ended banner */}
        {conversation.isAtLimit && (
          <ConversationEnded onStartNew={handleNewChat} />
        )}

        <div ref={threadEndRef} />
      </div>
    </>
  );
}
