"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Mode = "consumer" | "attorney";

interface ModeContextValue {
  mode: Mode;
  setMode: (mode: Mode) => void;
}

const ModeContext = createContext<ModeContextValue | null>(null);

function readStoredMode(): Mode {
  if (typeof window === "undefined") return "consumer";
  const stored = localStorage.getItem("eh-mode");
  return stored === "consumer" || stored === "attorney" ? stored : "consumer";
}

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<Mode>(readStoredMode);

  const setMode = useCallback((newMode: Mode) => {
    setModeState(newMode);
    localStorage.setItem("eh-mode", newMode);
    document.documentElement.setAttribute("data-mode", newMode);
  }, []);

  // Keep data-mode in sync (covers initial mount and hydration)
  useEffect(() => {
    document.documentElement.setAttribute("data-mode", mode);
  }, [mode]);

  return (
    <ModeContext.Provider value={{ mode, setMode }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode(): ModeContextValue {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error("useMode must be used within ModeProvider");
  return ctx;
}
