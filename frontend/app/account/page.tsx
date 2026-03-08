import type { Metadata } from "next";
import AccountContent from "./account-content";

export const metadata: Metadata = {
  title: "Account — Employee Help",
  description: "Manage your account settings and active sessions.",
};

export default function AccountPage() {
  return <AccountContent />;
}
