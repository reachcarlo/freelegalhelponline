"use client";

import { useCallback, useState } from "react";

interface DefinitionEditorProps {
  definitions: Record<string, string>;
  onSetDefinition: (term: string, definition: string) => void;
  onRemoveDefinition: (term: string) => void;
  includeDefinitions: boolean;
  onIncludeChange: (include: boolean) => void;
}

const inputCls =
  "w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none transition-colors";

export default function DefinitionEditor({
  definitions,
  onSetDefinition,
  onRemoveDefinition,
  includeDefinitions,
  onIncludeChange,
}: DefinitionEditorProps) {
  const [newTerm, setNewTerm] = useState("");
  const [newDef, setNewDef] = useState("");

  const entries = Object.entries(definitions);

  const handleAdd = useCallback(() => {
    const term = newTerm.trim();
    const def = newDef.trim();
    if (!term || !def) return;
    onSetDefinition(term, def);
    setNewTerm("");
    setNewDef("");
  }, [newTerm, newDef, onSetDefinition]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAdd();
      }
    },
    [handleAdd]
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">
          Legal Definitions
        </h3>
        <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={includeDefinitions}
            onChange={(e) => onIncludeChange(e.target.checked)}
            className="rounded border-border"
          />
          Include in document
        </label>
      </div>

      <p className="text-xs text-text-tertiary mb-4">
        Standard definitions are included automatically. Add custom definitions
        below if needed.
      </p>

      {/* Existing definitions */}
      {entries.length > 0 && (
        <div className="mb-4 space-y-2">
          {entries.map(([term, def]) => (
            <div
              key={term}
              className="flex items-start gap-2 rounded-lg border border-border p-3"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {term}
                </p>
                <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                  {def}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onRemoveDefinition(term)}
                className="mt-0.5 min-h-[28px] min-w-[28px] rounded text-text-tertiary hover:text-error-text transition-colors shrink-0"
                aria-label={`Remove definition: ${term}`}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add new */}
      <div className="rounded-lg border border-dashed border-border p-3 space-y-2">
        <input
          type="text"
          value={newTerm}
          onChange={(e) => setNewTerm(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Term (e.g. EMPLOYER)"
          className={inputCls}
        />
        <textarea
          value={newDef}
          onChange={(e) => setNewDef(e.target.value)}
          placeholder="Definition text…"
          rows={2}
          className={`${inputCls} resize-none`}
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!newTerm.trim() || !newDef.trim()}
          className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
            newTerm.trim() && newDef.trim()
              ? "text-accent hover:bg-accent-surface"
              : "text-text-tertiary cursor-not-allowed"
          }`}
        >
          + Add Definition
        </button>
      </div>
    </div>
  );
}
