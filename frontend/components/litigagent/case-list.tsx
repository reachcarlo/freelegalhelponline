"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  CaseInfo,
  createCase,
  listCases,
  archiveCase,
} from "@/lib/litigagent-api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatRelative(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(iso);
}

export default function CaseList() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const loadCases = useCallback(async () => {
    try {
      setError(null);
      const data = await listCases("active");
      setCases(data.cases);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const c = await createCase(newName.trim(), newDesc.trim() || undefined);
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      router.push(`/tools/litigagent/${c.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  const handleArchive = async (e: React.MouseEvent, caseId: string) => {
    e.stopPropagation();
    if (!confirm("Archive this case? It can be restored later.")) return;
    try {
      await archiveCase(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to archive case");
    }
  };

  const inputCls =
    "w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none transition-colors";

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <Link href="/tools" className="hover:text-accent">
            Tools
          </Link>
          {" / "}
          <span className="text-text-primary">LITIGAGENT</span>
        </nav>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
              LITIGAGENT
            </h1>
            <p className="mt-2 text-text-secondary">
              Upload case files, extract text, and analyze with AI.
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="min-h-[44px] rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            + New Case
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-lg border border-error-border bg-error-bg px-4 py-3 text-sm text-error-text">
            {error}
          </div>
        )}

        {/* Create case form */}
        {showCreate && (
          <div className="mt-6 rounded-lg border border-border bg-surface p-5">
            <h2 className="text-lg font-semibold text-text-primary">
              Create New Case
            </h2>
            <div className="mt-4 space-y-3">
              <div>
                <label htmlFor="new_case_name" className="mb-1 block text-xs font-medium text-text-secondary">
                  Case Name *
                </label>
                <input
                  id="new_case_name"
                  type="text"
                  className={inputCls}
                  placeholder="e.g., Johnson v. Acme Corp"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-text-secondary">
                  Description (optional)
                </label>
                <textarea
                  className={inputCls}
                  placeholder="Brief case summary..."
                  rows={2}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim() || creating}
                  className="min-h-[44px] rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-accent/40"
                >
                  {creating ? "Creating..." : "Create Case"}
                </button>
                <button
                  onClick={() => {
                    setShowCreate(false);
                    setNewName("");
                    setNewDesc("");
                  }}
                  className="min-h-[44px] rounded-lg border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-surface"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="mt-12 text-center text-text-tertiary">
            Loading cases...
          </div>
        )}

        {/* Empty state */}
        {!loading && cases.length === 0 && !showCreate && (
          <div className="mt-12 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface">
              <svg
                className="h-8 w-8 text-text-tertiary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-text-primary">
              No cases yet
            </h3>
            <p className="mt-1 text-sm text-text-tertiary">
              Create a case to start uploading and analyzing files.
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 min-h-[44px] rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              + New Case
            </button>
          </div>
        )}

        {/* Case list */}
        {!loading && cases.length > 0 && (
          <div className="mt-8 space-y-3">
            {cases.map((c) => (
              <div
                key={c.id}
                onClick={() => router.push(`/tools/litigagent/${c.id}`)}
                className="group cursor-pointer rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-base font-semibold text-text-primary group-hover:text-accent">
                      {c.name}
                    </h3>
                    {c.description && (
                      <p className="mt-1 truncate text-sm text-text-tertiary">
                        {c.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-4 text-xs text-text-tertiary">
                      <span>
                        {c.file_count} {c.file_count === 1 ? "file" : "files"}
                      </span>
                      <span>Updated {formatRelative(c.updated_at)}</span>
                      <span>Created {formatDate(c.created_at)}</span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleArchive(e, c.id)}
                    className="ml-4 rounded p-1.5 text-text-tertiary opacity-0 transition-all hover:bg-error-bg hover:text-error-text group-hover:opacity-100"
                    title="Archive case"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25-2.25M12 13.875V7.5M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
