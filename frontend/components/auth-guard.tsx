"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import AuthLoading from "@/components/auth-loading";

/**
 * Client-side auth guard. Redirects to /login if user is not authenticated.
 * Use this to wrap protected page content as a second layer of defense
 * (Next.js middleware handles the primary redirect).
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, user, router, pathname]);

  if (isLoading) {
    return <AuthLoading />;
  }

  if (!user) return null;

  return <>{children}</>;
}
