"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  provider: "google" | "microsoft";
  organization: {
    id: string;
    name: string;
    slug: string;
    plan_tier: string;
  } | null;
  role: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const didRedirect = useRef(false);

  const fetchUser = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        return data;
      }
      setUser(null);
      return null;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Clear local state regardless
    }
    setUser(null);
    router.push("/");
  }, [router]);

  // Fetch user on mount + handle post-OAuth redirect
  useEffect(() => {
    fetchUser().then((u) => {
      if (u && !didRedirect.current) {
        didRedirect.current = true;
        const redirect = sessionStorage.getItem("eh-auth-redirect");
        if (redirect) {
          sessionStorage.removeItem("eh-auth-redirect");
          router.push(redirect);
        }
      }
    });
  }, [fetchUser, router]);

  // Refresh access token every 12 minutes (before 15-min expiry)
  useEffect(() => {
    if (!user) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) setUser(null);
      } catch {
        // Ignore refresh errors
      }
    }, 12 * 60 * 1000);
    return () => clearInterval(timer);
  }, [user]);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, logout, refreshUser: fetchUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/**
 * Redirect to login page when a 401 is received from a protected API call.
 * Call this from API error handlers for protected endpoints.
 */
export function handleAuthError() {
  if (typeof window !== "undefined") {
    const redirect = window.location.pathname;
    window.location.href = `/login?redirect=${encodeURIComponent(redirect)}`;
  }
}
