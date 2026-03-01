import Link from "next/link";

export default function Disclaimer() {
  return (
    <div className="border-t border-warning-border bg-warning-bg px-4 py-3 text-center text-xs text-warning-text">
      <p>
        <strong>Legal Disclaimer:</strong> This tool provides general
        information about California employment law for educational purposes
        only. It does not constitute legal advice, and no attorney-client
        relationship is created by using this service. For advice about your
        specific situation, consult a licensed California employment attorney.
        {" "}
        <Link
          href="/terms"
          className="underline hover:opacity-80"
        >
          Terms of Use
        </Link>
        {" · "}
        <Link
          href="/privacy"
          className="underline hover:opacity-80"
        >
          Privacy Policy
        </Link>
      </p>
    </div>
  );
}
