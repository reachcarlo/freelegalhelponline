"use client";

import { createContext, useCallback, useContext, useRef } from "react";

// ── Types ────────────────────────────────────────────────────────

type ToolState = Record<string, unknown>;

interface WorkspaceContextValue {
  caseId: string;
  /** Retrieve persisted state for a tool. Returns {} if none saved. */
  getToolState: <T extends ToolState>(tool: string) => T;
  /** Merge a partial update into the persisted state for a tool. */
  setToolState: (tool: string, patch: ToolState) => void;
}

// ── Context ──────────────────────────────────────────────────────

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

/**
 * WorkspaceProvider — wraps the case workspace layout to preserve
 * per-tool state across route transitions.
 *
 * State is stored in a ref so writes never cause re-renders.
 * Each tool reads its state on mount and writes on unmount / change.
 */
export function WorkspaceProvider({
  caseId,
  children,
}: {
  caseId: string;
  children: React.ReactNode;
}) {
  const storeRef = useRef<Map<string, ToolState>>(new Map());

  const getToolState = useCallback(
    <T extends ToolState>(tool: string): T =>
      (storeRef.current.get(tool) ?? {}) as T,
    [],
  );

  const setToolState = useCallback((tool: string, patch: ToolState) => {
    const prev = storeRef.current.get(tool) ?? {};
    storeRef.current.set(tool, { ...prev, ...patch });
  }, []);

  return (
    <WorkspaceContext.Provider value={{ caseId, getToolState, setToolState }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

// ── Hooks ────────────────────────────────────────────────────────

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx)
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}

/** Returns context or null when outside the provider (legacy routes). */
export function useWorkspaceOptional() {
  return useContext(WorkspaceContext);
}

/**
 * Convenience hook for a single tool's state slice.
 *
 * Returns `[get, set]` where `get()` reads the current snapshot
 * and `set(patch)` merges a partial update.
 */
export function useToolState<T extends ToolState>(tool: string) {
  const { getToolState, setToolState } = useWorkspace();
  const get = useCallback(() => getToolState<T>(tool), [getToolState, tool]);
  const set = useCallback(
    (patch: Partial<T>) => setToolState(tool, patch as ToolState),
    [setToolState, tool],
  );
  return [get, set] as const;
}

/**
 * Like useToolState but returns no-op functions outside WorkspaceProvider.
 * Safe to use in components rendered both inside and outside the workspace.
 */
export function useToolStateOptional<T extends ToolState>(tool: string) {
  const ctx = useContext(WorkspaceContext);
  const noopGet = useCallback(() => ({}) as T, []);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const noopSet = useCallback((_patch: Partial<T>) => {}, []);

  const get = useCallback(
    () => (ctx ? (ctx.getToolState<T>(tool)) : ({} as T)),
    [ctx, tool],
  );
  const set = useCallback(
    (patch: Partial<T>) => ctx?.setToolState(tool, patch as ToolState),
    [ctx, tool],
  );

  return ctx ? ([get, set] as const) : ([noopGet, noopSet] as const);
}
