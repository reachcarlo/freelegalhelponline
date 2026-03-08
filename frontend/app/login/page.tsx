import { Suspense } from "react";
import { Metadata } from "next";
import LoginForm from "@/components/login-form";

export const metadata: Metadata = {
  title: "Sign In — Employee Help",
  description:
    "Sign in to access LITIGAGENT, discovery tools, and other attorney features.",
};

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center">
          <div className="text-text-tertiary">Loading...</div>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
