import { Metadata } from "next";
import Link from "next/link";
import GuidedIntake from "@/components/guided-intake";

export const metadata: Metadata = {
  title: "Not Sure Where to Start? — California Employment Rights",
  description:
    "Answer a few simple questions about your workplace situation to identify your employment law issue and find the right tools. Free guided intake questionnaire for California workers.",
  openGraph: {
    title: "Guided Intake — California Employment Rights",
    description:
      "Answer a few simple questions to identify your employment issue and find the right tools.",
    type: "website",
  },
};

export default function GuidedIntakePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <Link href="/tools" className="hover:text-accent">
            Tools
          </Link>
          {" / "}
          <span className="text-text-primary">Guided Intake</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Not Sure Where to Start?
        </h1>
        <p className="mt-4 text-lg text-text-secondary">
          Answer a few simple questions about your workplace situation. We will
          help you identify your employment law issue and recommend the right
          tools.
        </p>

        <div className="mt-8">
          <GuidedIntake />
        </div>

        <div className="mt-8 rounded-lg border border-warning-border bg-warning-bg p-4 text-sm text-warning-text">
          <strong>Important:</strong> This questionnaire provides general
          guidance to help you identify potential employment law issues based on
          your answers. It is not legal advice. Employment law is complex, and
          your specific facts may lead to different conclusions. Consult a
          licensed California employment attorney for advice about your specific
          situation.
        </div>
      </div>
    </div>
  );
}
