"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const ERROR_MESSAGES: Record<string, string> = {
  oauth_denied: "Sign-in was cancelled. Please try again.",
  missing_params: "Something went wrong with the sign-in. Please try again.",
  invalid_state: "Sign-in session expired. Please try again.",
  auth_failed: "Authentication failed. Please try again.",
};

export default function LoginForm() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const redirect = searchParams.get("redirect");

  // Store redirect target for post-OAuth navigation
  useEffect(() => {
    if (redirect) {
      sessionStorage.setItem("eh-auth-redirect", redirect);
    }
  }, [redirect]);

  // Already authenticated — redirect
  useEffect(() => {
    if (!isLoading && user) {
      router.push(redirect || "/");
    }
  }, [isLoading, user, router, redirect]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-text-tertiary">Loading...</div>
      </div>
    );
  }

  if (user) return null;

  return (
    <div className="flex flex-1 items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Branding */}
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
            Employee Help
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            California Employment Law
          </p>
          <p className="text-sm text-text-secondary">
            AI-Powered Legal Guidance
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div
            role="alert"
            className="mt-6 rounded-lg border border-error-border bg-error-bg p-3 text-center text-sm text-error-text"
          >
            {ERROR_MESSAGES[error] || "An error occurred. Please try again."}
          </div>
        )}

        {/* OAuth buttons */}
        <div className="mt-8 flex flex-col gap-3">
          <a
            href="/api/auth/google/login"
            className="flex items-center justify-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-surface-raised focus:outline-none focus:ring-2 focus:ring-accent/30"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              aria-hidden="true"
            >
              <path
                d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
                fill="#4285F4"
              />
              <path
                d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"
                fill="#34A853"
              />
              <path
                d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
                fill="#FBBC05"
              />
              <path
                d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
                fill="#EA4335"
              />
            </svg>
            Sign in with Google
          </a>

          <a
            href="/api/auth/microsoft/login"
            className="flex items-center justify-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-surface-raised focus:outline-none focus:ring-2 focus:ring-accent/30"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 21 21"
              aria-hidden="true"
            >
              <rect x="1" y="1" width="9" height="9" fill="#f25022" />
              <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
              <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
              <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
            </svg>
            Sign in with Microsoft
          </a>
        </div>

        {/* Trust signals */}
        <div className="mt-8 space-y-2 text-center text-xs text-text-tertiary">
          <p>
            By signing in, you agree to our{" "}
            <a href="/terms" className="underline hover:text-accent">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/privacy" className="underline hover:text-accent">
              Privacy Policy
            </a>
            .
          </p>
          <p>
            Your files are encrypted and private. We never store your password.
          </p>
        </div>
      </div>
    </div>
  );
}
