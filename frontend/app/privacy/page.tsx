import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — Find Legal Help",
  description:
    "Privacy Policy for Find Legal Help (findlegalhelp.online). Learn what data we collect, how we use it, and your rights under the California Consumer Privacy Act (CCPA/CPRA).",
};

export default function PrivacyPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <span className="text-text-primary">Privacy Policy</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-text-tertiary">
          Last updated: February 2026
        </p>

        <div className="mt-8 space-y-8 text-text-secondary leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              1. Introduction
            </h2>
            <p className="mt-3">
              Find Legal Help (&quot;findlegalhelp.online,&quot; &quot;the
              Service,&quot; &quot;we,&quot; &quot;us,&quot; or &quot;our&quot;)
              is committed to protecting your privacy. This Privacy Policy
              explains what information we collect, how we use it, how long we
              retain it, and your rights under the California Consumer Privacy
              Act (CCPA) as amended by the California Privacy Rights Act (CPRA).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              2. Information We Collect
            </h2>
            <p className="mt-3">We collect the following categories of information:</p>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong>Queries and responses:</strong> The questions you submit
                and the AI-generated answers, including the mode used (consumer
                or attorney), number of sources retrieved, and response metadata
                (model, token count, cost, duration).
              </li>
              <li>
                <strong>Feedback:</strong> Thumbs up/down ratings you
                voluntarily provide on responses.
              </li>
              <li>
                <strong>IP addresses:</strong> Your IP address is collected for
                rate limiting and abuse prevention.
              </li>
              <li>
                <strong>Session data:</strong> A session identifier is generated
                for multi-turn conversations. This is not linked to any account
                or personal identity.
              </li>
              <li>
                <strong>Usage analytics:</strong> If you consent, we collect
                anonymized page views and interactions via Plausible Analytics, a
                privacy-focused analytics service that does not use cookies or
                track individuals across sites.
              </li>
            </ul>
            <p className="mt-3">
              We do <strong>not</strong> collect: names, email addresses, phone
              numbers, account credentials, payment information, or any other
              information that directly identifies you, unless you voluntarily
              include such information in a query.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              3. How We Use Your Information
            </h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong>Providing the Service:</strong> Processing your queries
                and generating AI-powered responses about California employment
                law.
              </li>
              <li>
                <strong>Quality improvement:</strong> Analyzing query patterns
                and feedback to improve answer accuracy, retrieval quality, and
                the knowledge base.
              </li>
              <li>
                <strong>Abuse prevention:</strong> Using IP addresses for rate
                limiting and preventing misuse of the Service.
              </li>
              <li>
                <strong>Error tracking:</strong> Monitoring application errors to
                maintain service reliability.
              </li>
              <li>
                <strong>Aggregate analytics:</strong> Understanding usage
                patterns (e.g., query volume, popular topics) to guide product
                development.
              </li>
            </ul>
            <p className="mt-3">
              We do <strong>not</strong> sell your personal information. We do{" "}
              <strong>not</strong> use your data for advertising. We do{" "}
              <strong>not</strong> share your queries with any third parties
              except as necessary to provide the Service (see Section 5).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              4. Data Retention
            </h2>
            <p className="mt-3">
              We retain your data according to the following schedule:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong>Full query logs (including IP addresses):</strong>{" "}
                Retained for <strong>90 days</strong> from the date of the query
                for quality improvement and debugging purposes.
              </li>
              <li>
                <strong>After 90 days:</strong> IP addresses and any personally
                identifiable information are permanently stripped. Anonymized
                query and response data is retained indefinitely for aggregate
                analytics and quality improvement.
              </li>
              <li>
                <strong>Feedback ratings:</strong> Retained indefinitely in
                anonymized form (linked to query ID, not to any personal
                identifier).
              </li>
              <li>
                <strong>Analytics data:</strong> Plausible Analytics retains
                anonymized, aggregate data only. No individual user data is
                stored by the analytics service.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              5. Third-Party Services
            </h2>
            <p className="mt-3">
              To provide the Service, we use the following third-party services:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong>Anthropic (Claude API):</strong> Your queries are sent to
                Anthropic&apos;s API to generate responses. Anthropic processes this
                data in accordance with their{" "}
                <a
                  href="https://www.anthropic.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline hover:text-accent-hover"
                >
                  Privacy Policy
                </a>
                . Anthropic does not use API inputs to train their models.
              </li>
              <li>
                <strong>Sentry:</strong> Error tracking to monitor and fix
                application issues. Sentry may receive error context (not query
                content) in accordance with their{" "}
                <a
                  href="https://sentry.io/privacy/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline hover:text-accent-hover"
                >
                  Privacy Policy
                </a>
                .
              </li>
              <li>
                <strong>Plausible Analytics:</strong> Privacy-focused, cookie-free
                analytics. Plausible does not collect personal data or track users
                across sites. See their{" "}
                <a
                  href="https://plausible.io/data-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline hover:text-accent-hover"
                >
                  Data Policy
                </a>
                .
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              6. Your Rights Under CCPA/CPRA
            </h2>
            <p className="mt-3">
              If you are a California resident, you have the following rights
              under the California Consumer Privacy Act (Civil Code
              &sect;&sect; 1798.100&ndash;1798.199.100):
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong>Right to Know:</strong> You may request that we disclose
                the categories and specific pieces of personal information we
                have collected about you, the sources from which it was
                collected, the business purpose for collection, and the
                categories of third parties with whom it was shared.
              </li>
              <li>
                <strong>Right to Delete:</strong> You may request that we delete
                personal information we have collected from you, subject to
                certain exceptions (e.g., completing a transaction, detecting
                security incidents, complying with legal obligations).
              </li>
              <li>
                <strong>Right to Correct:</strong> You may request that we
                correct inaccurate personal information we maintain about you.
              </li>
              <li>
                <strong>Right to Opt-Out of Sale/Sharing:</strong> We do not
                sell or share your personal information for cross-context
                behavioral advertising. No opt-out is necessary.
              </li>
              <li>
                <strong>Right to Non-Discrimination:</strong> We will not
                discriminate against you for exercising any of your CCPA rights.
              </li>
              <li>
                <strong>Right to Limit Use of Sensitive Information:</strong> We
                do not collect sensitive personal information as defined by the
                CPRA.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              7. Exercising Your Rights
            </h2>
            <p className="mt-3">
              To exercise any of your rights described above, you may contact us
              at:{" "}
              <a
                href="mailto:privacy@findlegalhelp.online"
                className="text-accent underline hover:text-accent-hover"
              >
                privacy@findlegalhelp.online
              </a>
            </p>
            <p className="mt-3">
              We will respond to verifiable consumer requests within 45 days. If
              we need more time (up to an additional 45 days), we will notify
              you of the reason and the extension period.
            </p>
            <p className="mt-3">
              Because we do not require accounts and collect minimal identifying
              information, we may ask you to provide sufficient information to
              verify your identity and locate your data (e.g., the approximate
              date and content of queries you submitted).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              8. Cookies and Tracking
            </h2>
            <p className="mt-3">
              The Service does not use cookies for tracking purposes. We use
              browser localStorage to remember your display preferences (e.g.,
              consumer/attorney mode selection). This data never leaves your
              device.
            </p>
            <p className="mt-3">
              Plausible Analytics operates without cookies and does not track
              users across websites.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              9. Data Security
            </h2>
            <p className="mt-3">
              We implement reasonable security measures to protect your
              information, including encrypted connections (HTTPS), access
              controls, and secure hosting infrastructure. However, no method of
              electronic transmission or storage is 100% secure.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              10. Children&apos;s Privacy
            </h2>
            <p className="mt-3">
              The Service is not directed at children under 13. We do not
              knowingly collect personal information from children under 13. If
              we learn that we have collected such information, we will delete it
              promptly.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              11. Changes to This Policy
            </h2>
            <p className="mt-3">
              We may update this Privacy Policy from time to time. Changes will
              be posted on this page with an updated &quot;Last updated&quot;
              date. Your continued use of the Service after any changes
              constitutes acceptance of the updated policy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-text-primary">
              12. Contact Us
            </h2>
            <p className="mt-3">
              If you have questions about this Privacy Policy or our data
              practices, please contact us at:{" "}
              <a
                href="mailto:privacy@findlegalhelp.online"
                className="text-accent underline hover:text-accent-hover"
              >
                privacy@findlegalhelp.online
              </a>
            </p>
          </section>
        </div>

        <div className="mt-10 flex gap-4">
          <Link
            href="/terms"
            className="text-sm text-accent underline hover:text-accent-hover"
          >
            Terms of Use
          </Link>
          <Link
            href="/"
            className="text-sm text-accent underline hover:text-accent-hover"
          >
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
