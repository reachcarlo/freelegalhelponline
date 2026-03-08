"use client";

import { useCallback, useEffect, useState } from "react";

interface SessionInfo {
  id: string;
  ip_address: string | null;
  browser: string;
  os: string;
  device: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  is_current: boolean;
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString();
}

function DeviceIcon({ device }: { device: string }) {
  if (device === "Mobile") {
    return (
      <svg className="h-5 w-5 text-text-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
      </svg>
    );
  }
  if (device === "Tablet") {
    return (
      <svg className="h-5 w-5 text-text-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5h3m-6.75 2.25h10.5a2.25 2.25 0 002.25-2.25V4.5a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 4.5v15a2.25 2.25 0 002.25 2.25z" />
      </svg>
    );
  }
  // Desktop
  return (
    <svg className="h-5 w-5 text-text-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25A2.25 2.25 0 015.25 3h13.5A2.25 2.25 0 0121 5.25z" />
    </svg>
  );
}

export default function ActiveSessions() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/sessions", { credentials: "include" });
      if (!res.ok) throw new Error("Failed to load sessions");
      const data = await res.json();
      setSessions(data.sessions);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleRevoke = useCallback(async (sessionId: string) => {
    setRevoking(sessionId);
    try {
      const res = await fetch(`/api/auth/sessions/${sessionId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to revoke session");
      }
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke session");
    } finally {
      setRevoking(null);
    }
  }, []);

  const handleRevokeAll = useCallback(async () => {
    setRevoking("all");
    try {
      const res = await fetch("/api/auth/sessions", {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to revoke sessions");
      setSessions((prev) => prev.filter((s) => s.is_current));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke sessions");
    } finally {
      setRevoking(null);
    }
  }, []);

  const otherSessions = sessions.filter((s) => !s.is_current);

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6">
        <p className="text-sm text-text-tertiary">Loading sessions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6">
        <p className="text-sm text-red-600">{error}</p>
        <button
          onClick={fetchSessions}
          className="mt-2 text-sm text-accent hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">
          Active Sessions
        </h2>
        {otherSessions.length > 0 && (
          <button
            onClick={handleRevokeAll}
            disabled={revoking !== null}
            className="rounded-md px-3 py-1.5 text-sm text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
          >
            Revoke all other sessions
          </button>
        )}
      </div>

      <div className="space-y-3">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`flex items-center gap-4 rounded-lg border p-4 ${
              session.is_current
                ? "border-accent/30 bg-accent/5"
                : "border-border bg-surface"
            }`}
          >
            <DeviceIcon device={session.device} />

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-text-primary">
                  {session.browser} on {session.os}
                </p>
                {session.is_current && (
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                    Current
                  </span>
                )}
              </div>
              <p className="text-xs text-text-tertiary">
                {session.ip_address || "Unknown IP"}
                {" \u00B7 "}
                Last active {formatRelative(session.last_used_at)}
                {" \u00B7 "}
                Signed in {formatRelative(session.created_at)}
              </p>
            </div>

            {!session.is_current && (
              <button
                onClick={() => handleRevoke(session.id)}
                disabled={revoking !== null}
                className="shrink-0 rounded-md px-3 py-1.5 text-sm text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
              >
                {revoking === session.id ? "Revoking..." : "Revoke"}
              </button>
            )}
          </div>
        ))}
      </div>

      {sessions.length === 0 && (
        <p className="text-sm text-text-tertiary">No active sessions found.</p>
      )}
    </div>
  );
}
