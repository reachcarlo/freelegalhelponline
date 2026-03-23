"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  CaseFileInfo,
  ChatDoneMetadata,
  ChatSessionInfo,
  ChatSourceInfo,
  ChatTurnItem,
  chatWithCase,
  deleteChatSession,
  getChatHistory,
  listChatSessions,
  listFiles,
} from "@/lib/litigagent-api";
import { useToolStateOptional } from "@/lib/workspace-context";
import {
  ChatMessage,
  computeSuggestions,
  formatSessionDate,
} from "./chat-drawer";

interface ChatToolState {
  [key: string]: unknown;
  messages?: ChatMessage[];
  sessionId?: string | null;
  input?: string;
}

interface ChatPanelProps {
  caseId: string;
}

/**
 * Full-panel chat for the /cases/[caseId]/chat route.
 *
 * Reuses shared helpers from chat-drawer but renders as an inline
 * flex-column panel instead of a fixed-position overlay.
 */
export default function ChatPanel({ caseId }: ChatPanelProps) {
  const [getChatState, setChatState] = useToolStateOptional<ChatToolState>("chat");

  // Restore persisted state from workspace context on mount
  const restored = getChatState();
  const [files, setFiles] = useState<CaseFileInfo[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>(restored.messages ?? []);
  const [sessionId, setSessionId] = useState<string | null>(restored.sessionId ?? null);
  const [input, setInput] = useState(restored.input ?? "");
  const [streaming, setStreaming] = useState(false);
  const hadRestoredMessages = useRef(
    (restored.messages?.length ?? 0) > 0,
  );
  const [error, setError] = useState<string | null>(null);
  const [turnLimitReached, setTurnLimitReached] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionPreviews, setSessionPreviews] = useState<
    Record<string, string>
  >({});

  const suggestions = useMemo(() => computeSuggestions(files), [files]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Persist state to workspace context on change
  useEffect(() => {
    setChatState({ messages, sessionId, input });
  }, [messages, sessionId, input, setChatState]);

  // Load files for suggestions context
  useEffect(() => {
    listFiles(caseId)
      .then(setFiles)
      .catch(() => {});
  }, [caseId]);

  // Auto-scroll
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input on mount
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 200);
  }, []);

  // Load most recent session (skip if state was restored from context)
  useEffect(() => {
    if (hadRestoredMessages.current) return;
    (async () => {
      try {
        const s = await listChatSessions(caseId);
        if (s.length === 0 || s[0].turn_count === 0) return;
        const latest = s[0];
        const turns = await getChatHistory(caseId, latest.id);
        setSessionId(latest.id);
        setMessages(
          turns.map((t) => ({
            role: t.role as "user" | "assistant",
            content: t.content,
          }))
        );
      } catch {
        // start fresh
      }
    })();
  }, [caseId]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const buildHistory = useCallback(
    (): ChatTurnItem[] =>
      messages.map((m) => ({ role: m.role, content: m.content })),
    [messages]
  );

  const handleSend = useCallback(
    (query?: string) => {
      const text = (query || input).trim();
      if (!text || streaming || turnLimitReached) return;

      setInput("");
      setError(null);

      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      setStreaming(true);

      const history = buildHistory();

      const controller = chatWithCase(
        caseId,
        text,
        {
          onSources: (caseSources: ChatSourceInfo[], kbSources: ChatSourceInfo[]) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  caseSources,
                  kbSources,
                };
              }
              return updated;
            });
          },
          onToken: (text: string) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + text,
                };
              }
              return updated;
            });
          },
          onDone: (metadata: ChatDoneMetadata) => {
            setSessionId(metadata.session_id);
            if (metadata.is_final_turn) setTurnLimitReached(true);
            setStreaming(false);
            abortRef.current = null;
          },
          onError: (message: string) => {
            if (message === "TURN_LIMIT_EXCEEDED") {
              setTurnLimitReached(true);
              setMessages((prev) => {
                if (
                  prev.length >= 2 &&
                  prev[prev.length - 1].role === "assistant" &&
                  prev[prev.length - 1].content === ""
                ) {
                  return prev.slice(0, -2);
                }
                return prev;
              });
            } else {
              setError(message);
              setMessages((prev) => {
                if (
                  prev.length >= 1 &&
                  prev[prev.length - 1].role === "assistant" &&
                  prev[prev.length - 1].content === ""
                ) {
                  return prev.slice(0, -1);
                }
                return prev;
              });
            }
            setStreaming(false);
            abortRef.current = null;
          },
        },
        {
          session_id: sessionId || undefined,
          conversation_history: history.length > 0 ? history : undefined,
        }
      );

      abortRef.current = controller;
    },
    [input, streaming, turnLimitReached, caseId, sessionId, buildHistory]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
    abortRef.current = null;
  }, []);

  const handleNewSession = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setSessionId(null);
    setError(null);
    setTurnLimitReached(false);
    setStreaming(false);
    setShowHistory(false);
    abortRef.current = null;
  }, []);

  const handleToggleHistory = useCallback(async () => {
    const newShow = !showHistory;
    setShowHistory(newShow);
    if (!newShow) return;

    setSessionsLoading(true);
    try {
      const fetched = await listChatSessions(caseId);
      setSessions(fetched);

      const previews: Record<string, string> = { ...sessionPreviews };
      const toFetch = fetched.filter(
        (s) => s.turn_count > 0 && !previews[s.id]
      );
      await Promise.all(
        toFetch.map(async (s) => {
          try {
            const turns = await getChatHistory(caseId, s.id);
            const firstUser = turns.find((t) => t.role === "user");
            if (firstUser) previews[s.id] = firstUser.content;
          } catch {
            // ignore
          }
        })
      );
      setSessionPreviews(previews);
    } catch {
      // silently fail
    } finally {
      setSessionsLoading(false);
    }
  }, [showHistory, caseId, sessionPreviews]);

  const handleSwitchSession = useCallback(
    async (targetSessionId: string) => {
      if (targetSessionId === sessionId) {
        setShowHistory(false);
        return;
      }
      try {
        const turns = await getChatHistory(caseId, targetSessionId);
        abortRef.current?.abort();
        setMessages(
          turns.map((t) => ({
            role: t.role as "user" | "assistant",
            content: t.content,
          }))
        );
        setSessionId(targetSessionId);
        setError(null);
        setTurnLimitReached(false);
        setStreaming(false);
        setShowHistory(false);
        abortRef.current = null;
      } catch {
        // silently fail
      }
    },
    [caseId, sessionId]
  );

  const handleDeleteSession = useCallback(
    async (targetSessionId: string) => {
      try {
        await deleteChatSession(caseId, targetSessionId);
        setSessions((prev) => prev.filter((s) => s.id !== targetSessionId));
        if (targetSessionId === sessionId) {
          setMessages([]);
          setSessionId(null);
          setError(null);
          setTurnLimitReached(false);
        }
      } catch {
        // silently fail
      }
    },
    [caseId, sessionId]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="flex h-full flex-col bg-surface"
      data-testid="chat-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <svg
            className="h-5 w-5 text-accent"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
            />
          </svg>
          <h2 className="text-sm font-semibold text-text-primary">
            Chat with Case
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleToggleHistory}
            className={`rounded p-1.5 transition-colors ${
              showHistory
                ? "bg-accent/10 text-accent"
                : "text-text-tertiary hover:bg-accent-surface hover:text-accent"
            }`}
            title="Chat history"
            data-testid="chat-history-toggle"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </button>
          <button
            onClick={handleNewSession}
            className="rounded p-1.5 text-text-tertiary transition-colors hover:bg-accent-surface hover:text-accent"
            title="New conversation"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 4.5v15m7.5-7.5h-15"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Session history panel */}
      {showHistory && (
        <div
          className="border-b border-border bg-background"
          data-testid="session-history-panel"
        >
          <div className="px-4 py-2">
            <p className="text-xs font-medium text-text-tertiary">
              Previous conversations
            </p>
          </div>
          <div className="max-h-[240px] overflow-y-auto">
            {sessionsLoading ? (
              <div className="px-4 py-3 text-center">
                <p className="text-xs text-text-tertiary">Loading...</p>
              </div>
            ) : sessions.length === 0 ? (
              <div className="px-4 py-3 text-center">
                <p className="text-xs text-text-tertiary">
                  No previous conversations
                </p>
              </div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={`group flex items-center gap-2 border-b border-border/50 px-4 py-2.5 last:border-b-0 ${
                    s.id === sessionId
                      ? "bg-accent/5"
                      : "hover:bg-surface cursor-pointer"
                  }`}
                >
                  <button
                    className="flex-1 text-left"
                    onClick={() => handleSwitchSession(s.id)}
                  >
                    <p className="truncate text-sm text-text-primary">
                      {sessionPreviews[s.id] ||
                        `Conversation (${s.turn_count} ${s.turn_count === 1 ? "turn" : "turns"})`}
                    </p>
                    <p className="mt-0.5 text-[11px] text-text-tertiary">
                      {formatSessionDate(s.updated_at)}
                      {" \u00b7 "}
                      {s.turn_count} {s.turn_count === 1 ? "turn" : "turns"}
                      {s.id === sessionId && (
                        <span className="ml-1 text-accent">(current)</span>
                      )}
                    </p>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(s.id);
                    }}
                    className="rounded p-1 text-text-tertiary opacity-0 transition-opacity hover:bg-error-bg hover:text-error-text group-hover:opacity-100"
                    title="Delete conversation"
                  >
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                      />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {/* Empty state with suggestions */}
        {messages.length === 0 && !streaming && (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6">
            <div className="text-center">
              <p className="text-sm text-text-secondary">
                Ask questions about your case files. The AI will search your
                uploaded documents and legal knowledge base.
              </p>
            </div>
            <div className="flex w-full flex-col gap-2">
              <p className="text-xs font-medium text-text-tertiary">
                Suggested questions
              </p>
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="rounded-lg border border-border px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:border-accent hover:bg-accent-surface hover:text-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message list */}
        <div className="mx-auto max-w-2xl space-y-4">
          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent/10 px-4 py-2.5">
                    <p className="whitespace-pre-wrap text-sm text-text-primary">
                      {msg.content}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex justify-start">
                  <div className="max-w-[90%]">
                    <div className="rounded-2xl rounded-bl-md bg-background px-4 py-2.5">
                      {msg.content ? (
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                          {msg.content}
                          {streaming && i === messages.length - 1 && (
                            <span className="ml-0.5 inline-block animate-pulse">
                              |
                            </span>
                          )}
                        </p>
                      ) : streaming && i === messages.length - 1 ? (
                        <div className="flex items-center gap-1.5 py-1">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-tertiary [animation-delay:0ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-tertiary [animation-delay:150ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-tertiary [animation-delay:300ms]" />
                        </div>
                      ) : null}
                    </div>

                    {/* Sources */}
                    {(msg.caseSources?.length || msg.kbSources?.length) && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {msg.caseSources?.map((s, j) => (
                          <span
                            key={`cs-${j}`}
                            className="inline-flex items-center gap-1 rounded-full bg-accent/8 px-2 py-0.5 text-[11px] text-accent"
                            title={s.title}
                          >
                            <svg
                              className="h-3 w-3"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13"
                              />
                            </svg>
                            {s.title}
                          </span>
                        ))}
                        {msg.kbSources?.map((s, j) => (
                          <span
                            key={`kb-${j}`}
                            className="inline-flex items-center gap-1 rounded-full bg-text-tertiary/10 px-2 py-0.5 text-[11px] text-text-tertiary"
                            title={s.heading_path || s.title}
                          >
                            <svg
                              className="h-3 w-3"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
                              />
                            </svg>
                            {s.title}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mb-2 flex items-center justify-between rounded-lg border border-error-border bg-error-bg px-3 py-2">
          <p className="text-xs text-error-text">{error}</p>
          <button
            onClick={() => setError(null)}
            className="ml-2 text-error-text hover:opacity-70"
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      )}

      {/* Turn limit banner */}
      {turnLimitReached && (
        <div className="mx-4 mb-2 flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
          <p className="text-xs text-text-tertiary">
            Conversation limit reached.
          </p>
          <button
            onClick={handleNewSession}
            className="ml-2 text-xs font-medium text-accent hover:text-accent-hover"
          >
            New conversation
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-border px-4 py-3">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <textarea
            ref={inputRef}
            className="flex-1 resize-none rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            rows={1}
            placeholder={
              turnLimitReached
                ? "Start a new conversation..."
                : "Ask about this case..."
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={turnLimitReached}
            style={{
              maxHeight: "120px",
              minHeight: "38px",
              height: "auto",
              overflow: input.split("\n").length > 3 ? "auto" : "hidden",
            }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 120) + "px";
            }}
          />
          {streaming ? (
            <button
              onClick={handleStop}
              className="flex h-[38px] w-[38px] items-center justify-center rounded-lg bg-error-bg text-error-text transition-colors hover:bg-error-border"
              title="Stop generating"
            >
              <svg
                className="h-4 w-4"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || turnLimitReached}
              className="flex h-[38px] w-[38px] items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
              title="Send message"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                />
              </svg>
            </button>
          )}
        </div>
        <p className="mx-auto mt-1.5 max-w-2xl text-[11px] text-text-tertiary">
          Identifying information is obfuscated before AI processing.{" "}
          <Link
            href="/privacy#case-file-data"
            className="text-accent hover:text-accent-hover"
          >
            Details &rarr;
          </Link>
        </p>
      </div>
    </div>
  );
}
