"use client";

import { useCallback, useRef, useState } from "react";
import type { AskMetadata, ConversationTurn, SourceInfo } from "./api";

export interface CompletedTurn {
  query: string;
  answer: string;
  sources: SourceInfo[];
  metadata: AskMetadata | null;
}

const DEFAULT_MAX_TURNS: Record<string, number> = {
  consumer: 3,
  attorney: 5,
};

/** Timeout in ms — if no data arrives within this window, treat it as an error.
 *  Set to 45s to accommodate attorney mode (Sonnet 4.6 can take 35s+ for
 *  complex statutory analysis). Resets on every SSE event. */
const RESPONSE_TIMEOUT_MS = 45_000;

function generateSessionId(): string {
  return crypto.randomUUID();
}

export function useConversation(mode: "consumer" | "attorney") {
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [turns, setTurns] = useState<CompletedTurn[]>([]);
  const [currentTurn, setCurrentTurn] = useState(1);
  const [maxTurns, setMaxTurns] = useState(DEFAULT_MAX_TURNS[mode] ?? 3);
  const [isAtLimit, setIsAtLimit] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [streamingSources, setStreamingSources] = useState<SourceInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [streamingQuery, setStreamingQuery] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Refs for stable callbacks that capture latest streaming state
  const streamingAnswerRef = useRef("");
  const streamingSourcesRef = useRef<SourceInfo[]>([]);
  const streamingQueryRef = useRef("");

  const clearResponseTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const resetResponseTimeout = useCallback(() => {
    clearResponseTimeout();
    timeoutRef.current = setTimeout(() => {
      // No data received within the timeout window — abort and show error
      abortRef.current?.abort();
      setIsStreaming(false);
      setError("Response timed out. Please try again.");
    }, RESPONSE_TIMEOUT_MS);
  }, [clearResponseTimeout]);

  const buildConversationHistory = useCallback((): ConversationTurn[] => {
    const history: ConversationTurn[] = [];
    for (const turn of turns) {
      history.push({ role: "user", content: turn.query });
      history.push({ role: "assistant", content: turn.answer });
    }
    return history;
  }, [turns]);

  const startNewConversation = useCallback(() => {
    clearResponseTimeout();
    abortRef.current?.abort();
    setSessionId(generateSessionId());
    setTurns([]);
    setCurrentTurn(1);
    setMaxTurns(DEFAULT_MAX_TURNS[mode] ?? 3);
    setIsAtLimit(false);
    setIsStreaming(false);
    setStreamingAnswer("");
    setStreamingSources([]);
    setError(null);
    setStreamingQuery("");
  }, [mode, clearResponseTimeout]);

  const beginTurn = useCallback(
    (query: string) => {
      streamingQueryRef.current = query;
      streamingAnswerRef.current = "";
      streamingSourcesRef.current = [];
      setStreamingQuery(query);
      setStreamingAnswer("");
      setStreamingSources([]);
      setError(null);
      setIsStreaming(true);
      resetResponseTimeout();
    },
    [resetResponseTimeout]
  );

  const onSources = useCallback(
    (sources: SourceInfo[]) => {
      streamingSourcesRef.current = sources;
      setStreamingSources(sources);
      resetResponseTimeout(); // Data received — reset the clock
    },
    [resetResponseTimeout]
  );

  const onToken = useCallback(
    (text: string) => {
      streamingAnswerRef.current += text;
      setStreamingAnswer((prev) => prev + text);
      resetResponseTimeout(); // Data received — reset the clock
    },
    [resetResponseTimeout]
  );

  const onDone = useCallback(
    (metadata: AskMetadata) => {
      clearResponseTimeout();
      setIsStreaming(false);

      if (metadata.max_turns) {
        setMaxTurns(metadata.max_turns);
      }

      const completedTurn: CompletedTurn = {
        query: streamingQueryRef.current,
        answer: streamingAnswerRef.current,
        sources: streamingSourcesRef.current,
        metadata,
      };

      setTurns((prev) => [...prev, completedTurn]);

      if (metadata.is_final_turn) {
        setIsAtLimit(true);
      }

      setCurrentTurn((prev) => prev + 1);
    },
    [clearResponseTimeout]
  );

  const onError = useCallback(
    (message: string) => {
      clearResponseTimeout();
      setIsStreaming(false);
      if (message === "TURN_LIMIT_EXCEEDED") {
        setIsAtLimit(true);
        setError("You've reached the follow-up limit for this conversation.");
      } else {
        setError(message);
      }
    },
    [clearResponseTimeout]
  );

  return {
    sessionId,
    turns,
    currentTurn,
    maxTurns,
    isAtLimit,
    isStreaming,
    streamingAnswer,
    streamingSources,
    streamingQuery,
    error,
    abortRef,
    buildConversationHistory,
    startNewConversation,
    beginTurn,
    onSources,
    onToken,
    onDone,
    onError,
  };
}
