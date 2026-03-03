import { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllClaimSlugs, getClaimBySlug, claims } from "@/lib/claims";
import { topics } from "@/lib/topics";

interface ClaimPageProps {
  params: Promise<{ type: string }>;
}

export async function generateStaticParams() {
  return getAllClaimSlugs().map((type) => ({ type }));
}

export async function generateMetadata({
  params,
}: ClaimPageProps): Promise<Metadata> {
  const { type } = await params;
  const claim = getClaimBySlug(type);
  if (!claim) return {};

  return {
    title: `${claim.title} — Find Legal Help`,
    description: claim.metaDescription,
    openGraph: {
      title: claim.title,
      description: claim.metaDescription,
      type: "article",
    },
  };
}

export default async function ClaimPage({ params }: ClaimPageProps) {
  const { type } = await params;
  const claim = getClaimBySlug(type);
  if (!claim) notFound();

  const relatedClaims = claim.relatedClaimSlugs
    .map((s) => claims.find((c) => c.slug === s))
    .filter(Boolean);

  const relatedTopics = claim.relatedTopicSlugs
    .map((s) => topics.find((t) => t.slug === s))
    .filter(Boolean);

  // Schema.org FAQPage structured data
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: claim.faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };

  // Schema.org LegalService structured data
  const legalServiceSchema = {
    "@context": "https://schema.org",
    "@type": "LegalService",
    name: "Find Legal Help",
    serviceType: "Legal Information",
    areaServed: {
      "@type": "State",
      name: "California",
    },
    availableChannel: {
      "@type": "ServiceChannel",
      serviceUrl: "https://findlegalhelp.online/",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(legalServiceSchema),
        }}
      />

      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
          {/* Breadcrumb */}
          <nav className="mb-6 text-sm text-text-tertiary">
            <Link href="/" className="hover:text-accent">
              Home
            </Link>
            {" / "}
            <Link href="/claims" className="hover:text-accent">
              Claims
            </Link>
            {" / "}
            <span className="text-text-primary">{claim.shortTitle}</span>
          </nav>

          {/* Header */}
          <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
            {claim.title}
          </h1>
          <p className="mt-4 text-lg text-text-secondary">{claim.overview}</p>

          {/* Badges: agencies, statutes */}
          <div className="mt-4 flex flex-wrap gap-2">
            {claim.primaryAgencies.map((agency) => (
              <span
                key={agency}
                className="rounded-full bg-accent-surface px-3 py-1 text-xs font-medium text-accent"
              >
                {agency}
              </span>
            ))}
            {claim.relevantStatutes.map((statute) => (
              <span
                key={statute}
                className="rounded-full bg-badge-bg px-3 py-1 text-xs font-medium text-badge-text"
              >
                {statute}
              </span>
            ))}
          </div>

          {/* Elements of the claim */}
          <section className="mt-10">
            <h2 className="text-2xl font-semibold text-text-primary">
              Elements of the Claim
            </h2>
            <p className="mt-2 text-sm text-text-tertiary">
              To succeed on this claim, you generally must establish each of
              the following:
            </p>
            <ol className="mt-4 space-y-4">
              {claim.elements.map((el, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-border bg-surface-raised p-5"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">
                      {i + 1}
                    </span>
                    <div>
                      <h3 className="font-medium text-text-primary">
                        {el.element}
                      </h3>
                      <p className="mt-1 text-sm text-text-secondary leading-relaxed">
                        {el.description}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* Filing deadlines */}
          <section className="mt-10">
            <h2 className="text-2xl font-semibold text-text-primary">
              Filing Deadlines
            </h2>
            <p className="mt-2 text-sm text-text-tertiary">
              Missing a deadline can bar your claim. Act promptly and consult
              an attorney if deadlines are approaching.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {claim.deadlines.map((dl, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border bg-surface-raised p-5"
                >
                  <p className="text-sm font-medium text-text-primary">
                    {dl.name}
                  </p>
                  <p className="mt-1 text-2xl font-bold text-accent">
                    {dl.period}
                  </p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {dl.statute}
                  </p>
                  {dl.notes && (
                    <p className="mt-2 text-sm text-text-secondary">
                      {dl.notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* FAQ section */}
          <section className="mt-10">
            <h2 className="text-2xl font-semibold text-text-primary">
              Frequently Asked Questions
            </h2>
            <div className="mt-6 space-y-6">
              {claim.faqs.map((faq, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border bg-surface-raised p-6"
                >
                  <h3 className="text-lg font-medium text-text-primary">
                    {faq.question}
                  </h3>
                  <p className="mt-3 text-text-secondary leading-relaxed">
                    {faq.answer}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* CTA */}
          <section className="mt-10 rounded-lg bg-accent-surface p-6 text-center">
            <h2 className="text-lg font-semibold text-text-primary">
              Think you may have a claim?
            </h2>
            <p className="mt-2 text-text-secondary">
              Ask our AI-powered assistant about your California employment
              rights.
            </p>
            <Link
              href="/"
              className="mt-4 inline-block rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-accent-hover"
            >
              {claim.ctaQuery}
            </Link>
          </section>

          {/* Related claims */}
          {relatedClaims.length > 0 && (
            <section className="mt-10">
              <h2 className="text-lg font-semibold text-text-primary">
                Related Claims
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {relatedClaims.map(
                  (rc) =>
                    rc && (
                      <Link
                        key={rc.slug}
                        href={`/claims/${rc.slug}`}
                        className="rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface"
                      >
                        <span className="font-medium text-text-primary">
                          {rc.shortTitle}
                        </span>
                        <p className="mt-1 text-sm text-text-tertiary">
                          {rc.description}
                        </p>
                      </Link>
                    )
                )}
              </div>
            </section>
          )}

          {/* Related topics */}
          {relatedTopics.length > 0 && (
            <section className="mt-10">
              <h2 className="text-lg font-semibold text-text-primary">
                Related Topics
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {relatedTopics.map(
                  (rt) =>
                    rt && (
                      <Link
                        key={rt.slug}
                        href={`/topics/${rt.slug}`}
                        className="rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface"
                      >
                        <span className="font-medium text-text-primary">
                          {rt.shortTitle}
                        </span>
                        <p className="mt-1 text-sm text-text-tertiary">
                          {rt.description}
                        </p>
                      </Link>
                    )
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
