import { Suspense } from "react";
import { Metadata } from "next";
import LoginForm from "@/components/login-form";
import AuthLoading from "@/components/auth-loading";

export const metadata: Metadata = {
  title: "Sign In — Employee Help",
  description:
    "Sign in to access LITIGAGENT, discovery tools, and other attorney features.",
};

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthLoading message="Loading..." />}>
      <LoginForm />
    </Suspense>
  );
}
