"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function SignedOutBanner() {
  const searchParams = useSearchParams();
  const isSignedOut = searchParams.get("signed_out") === "1";
  const [dismissed, setDismissed] = useState(false);
  const cleanedRef = useRef(false);

  // Clean URL and auto-dismiss after 3s
  useEffect(() => {
    if (!isSignedOut || cleanedRef.current) return;
    cleanedRef.current = true;
    window.history.replaceState({}, "", "/");
    const timer = setTimeout(() => setDismissed(true), 3000);
    return () => clearTimeout(timer);
  }, [isSignedOut]);

  if (!isSignedOut || dismissed) return null;

  return (
    <div
      role="status"
      className="bg-surface-raised text-text-secondary text-sm text-center py-2 animate-fade-in"
    >
      You&apos;ve been signed out.
    </div>
  );
}
