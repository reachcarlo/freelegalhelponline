import { Metadata } from "next";
import CaseList from "@/components/litigagent/case-list";

export const metadata: Metadata = {
  title: "LITIGAGENT — Case File Analysis",
  description:
    "Upload case files, extract text automatically, and analyze with AI. Supports PDF, Word, email, and more.",
};

export default function LitigagentPage() {
  return <CaseList />;
}
