"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth, type AuthUser } from "@/lib/auth-context";

function UserAvatar({
  user,
  size = 32,
}: {
  user: Pick<AuthUser, "display_name" | "avatar_url" | "email">;
  size?: number;
}) {
  const initials = (user.display_name || user.email)
    .split(/[\s@]/)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() || "")
    .join("");

  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt=""
        width={size}
        height={size}
        className="rounded-full"
        referrerPolicy="no-referrer"
      />
    );
  }

  return (
    <div
      className="flex items-center justify-center rounded-full bg-accent text-white text-xs font-medium"
      style={{ width: size, height: size }}
    >
      {initials}
    </div>
  );
}

export default function UserMenu() {
  const { user, isLoading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleToggle = useCallback(() => setOpen((v) => !v), []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  if (isLoading || !user) return null;

  return (
    <div ref={menuRef} className="fixed top-3 right-3 z-50">
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 rounded-full p-1 transition-colors hover:bg-surface-raised focus:outline-none focus:ring-2 focus:ring-accent/30"
        aria-label="User menu"
        aria-expanded={open}
      >
        <UserAvatar user={user} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-lg border border-border bg-surface shadow-lg">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm font-medium text-text-primary truncate">
              {user.display_name || user.email}
            </p>
            <p className="text-xs text-text-tertiary truncate">{user.email}</p>
          </div>
          <div className="p-1">
            <button
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="w-full rounded-md px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-surface-raised hover:text-text-primary"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
