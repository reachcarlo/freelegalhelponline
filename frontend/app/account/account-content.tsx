"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import AuthGuard from "@/components/auth-guard";
import ActiveSessions from "@/components/active-sessions";

function ProviderBadge({ provider }: { provider: string }) {
  const label = provider === "google" ? "Google" : "Microsoft";
  return (
    <span className="rounded-full bg-surface-raised px-2.5 py-0.5 text-xs font-medium text-text-secondary">
      {label}
    </span>
  );
}

function AccountInner() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-8 px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Account</h1>
        <Link
          href="/"
          className="text-sm text-text-tertiary transition-colors hover:text-text-primary"
        >
          Back to home
        </Link>
      </div>

      {/* Profile section */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h2 className="mb-4 text-lg font-semibold text-text-primary">
          Profile
        </h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-tertiary">Name</span>
            <span className="text-sm font-medium text-text-primary">
              {user.display_name || "Not set"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-tertiary">Email</span>
            <span className="text-sm font-medium text-text-primary">
              {user.email}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-tertiary">Sign-in method</span>
            <ProviderBadge provider={user.provider} />
          </div>
          {user.organization && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-tertiary">Plan</span>
              <span className="text-sm font-medium text-text-primary capitalize">
                {user.organization.plan_tier}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Sessions section */}
      <ActiveSessions />
    </div>
  );
}

export default function AccountContent() {
  return (
    <AuthGuard>
      <AccountInner />
    </AuthGuard>
  );
}
