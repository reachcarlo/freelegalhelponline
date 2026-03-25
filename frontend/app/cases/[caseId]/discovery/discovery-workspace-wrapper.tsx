"use client";

import { useEffect, useState } from "react";
import { CaseContextInfo, getCaseContext } from "@/lib/litigagent-api";
import { DiscoveryProvider } from "@/lib/discovery-context";
import { useAuth } from "@/lib/auth-context";

/**
 * Wrapper that fetches the case context and passes it to DiscoveryProvider.
 *
 * Waits until the context is loaded before rendering children so the
 * provider's initial state includes pre-filled case info.
 */
export default function DiscoveryWorkspaceWrapper({
  caseId,
  children,
}: {
  caseId: string;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  const [caseContext, setCaseContext] = useState<CaseContextInfo | undefined>();
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getCaseContext(caseId)
      .then(setCaseContext)
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [caseId]);

  if (!loaded) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-text-tertiary">Loading case context...</p>
      </div>
    );
  }

  return (
    <DiscoveryProvider caseContext={caseContext} userEmail={user?.email}>
      {children}
    </DiscoveryProvider>
  );
}
