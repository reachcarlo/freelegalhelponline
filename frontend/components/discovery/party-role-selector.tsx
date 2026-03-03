"use client";

import type { PartyRole } from "@/lib/discovery-api";

interface PartyRoleSelectorProps {
  value: PartyRole;
  onChange: (role: PartyRole) => void;
}

const roles: { value: PartyRole; label: string; description: string }[] = [
  {
    value: "plaintiff",
    label: "Plaintiff",
    description: "You are the party who filed the lawsuit",
  },
  {
    value: "defendant",
    label: "Defendant",
    description: "You are the party being sued",
  },
];

export default function PartyRoleSelector({
  value,
  onChange,
}: PartyRoleSelectorProps) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-text-primary mb-3">
        Party Role
      </legend>
      <div className="grid grid-cols-2 gap-3">
        {roles.map((role) => {
          const selected = value === role.value;
          return (
            <button
              key={role.value}
              type="button"
              onClick={() => onChange(role.value)}
              className={`min-h-[44px] rounded-lg border p-3 text-left transition-colors ${
                selected
                  ? "border-accent bg-accent-surface"
                  : "border-border hover:border-border-hover"
              }`}
              aria-pressed={selected}
            >
              <span
                className={`text-sm font-medium ${
                  selected ? "text-accent" : "text-text-primary"
                }`}
              >
                {role.label}
              </span>
              <span className="mt-1 block text-xs text-text-tertiary">
                {role.description}
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
