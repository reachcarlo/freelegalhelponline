"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Mode = "consumer" | "attorney";

interface ConsentContextValue {
  hasConsentedForMode: (mode: Mode) => boolean;
  grantConsentForMode: (mode: Mode) => void;
}

const STORAGE_KEY_PREFIX = "eh-consent-";

const ConsentContext = createContext<ConsentContextValue | null>(null);

export function ConsentProvider({ children }: { children: React.ReactNode }) {
  const [consented, setConsented] = useState<Record<Mode, boolean>>({
    consumer: false,
    attorney: false,
  });

  useEffect(() => {
    setConsented({
      consumer: localStorage.getItem(`${STORAGE_KEY_PREFIX}consumer`) === "true",
      attorney: localStorage.getItem(`${STORAGE_KEY_PREFIX}attorney`) === "true",
    });
  }, []);

  const hasConsentedForMode = useCallback(
    (mode: Mode) => consented[mode],
    [consented]
  );

  const grantConsentForMode = useCallback((mode: Mode) => {
    setConsented((prev) => ({ ...prev, [mode]: true }));
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${mode}`, "true");
  }, []);

  return (
    <ConsentContext.Provider value={{ hasConsentedForMode, grantConsentForMode }}>
      {children}
    </ConsentContext.Provider>
  );
}

export function useConsent(): ConsentContextValue {
  const ctx = useContext(ConsentContext);
  if (!ctx) throw new Error("useConsent must be used within ConsentProvider");
  return ctx;
}
