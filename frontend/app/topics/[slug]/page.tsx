import { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllTopicSlugs, getTopicBySlug, topics } from "@/lib/topics";
import { getClaimsForTopic } from "@/lib/claims";

// ── Topic → relevant tools mapping ─────────────────────────────────

interface RelatedTool {
  href: string;
  title: string;
  description: string;
}

const ALL_TOOLS: Record<string, RelatedTool> = {
  "guided-intake": {
    href: "/tools/guided-intake",
    title: "Guided Intake",
    description: "Not sure about your issue? Answer a few questions to get personalized tool recommendations.",
  },
  "deadline-calculator": {
    href: "/tools/deadline-calculator",
    title: "Deadline Calculator",
    description: "Check your statute of limitations and filing deadlines.",
  },
  "agency-routing": {
    href: "/tools/agency-routing",
    title: "Agency Routing Guide",
    description: "Find which government agency handles your complaint.",
  },
  "unpaid-wages-calculator": {
    href: "/tools/unpaid-wages-calculator",
    title: "Unpaid Wages Calculator",
    description: "Estimate how much you may be owed including penalties.",
  },
  "incident-docs": {
    href: "/tools/incident-docs",
    title: "Incident Documentation",
    description: "Document what happened while details are fresh.",
  },
};

const TOPIC_TOOLS: Record<string, string[]> = {
  "wages-and-compensation": ["unpaid-wages-calculator", "deadline-calculator", "agency-routing", "incident-docs"],
  "discrimination-and-harassment": ["deadline-calculator", "agency-routing", "incident-docs"],
  "retaliation-and-whistleblower": ["deadline-calculator", "agency-routing", "incident-docs"],
  "leave-and-time-off": ["deadline-calculator", "agency-routing"],
  "workplace-safety": ["agency-routing", "incident-docs"],
  "workers-compensation": ["agency-routing"],
  "unemployment-benefits": ["agency-routing"],
  "employment-contracts": ["guided-intake"],
  "public-sector-employment": ["agency-routing"],
  "unfair-business-practices": ["deadline-calculator", "agency-routing"],
  "complaint-and-claims-process": ["deadline-calculator", "agency-routing", "guided-intake"],
};

interface TopicPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return getAllTopicSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: TopicPageProps): Promise<Metadata> {
  const { slug } = await params;
  const topic = getTopicBySlug(slug);
  if (!topic) return {};

  return {
    title: `${topic.title} — Find Legal Help`,
    description: topic.metaDescription,
    openGraph: {
      title: topic.title,
      description: topic.metaDescription,
      type: "article",
    },
  };
}

export default async function TopicPage({ params }: TopicPageProps) {
  const { slug } = await params;
  const topic = getTopicBySlug(slug);
  if (!topic) notFound();

  const related = topic.relatedTopics
    .map((s) => topics.find((t) => t.slug === s))
    .filter(Boolean);

  const relatedClaims = getClaimsForTopic(slug);

  // Schema.org FAQPage structured data
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: topic.faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-text-tertiary">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          {" / "}
          <Link href="/topics" className="hover:text-accent">
            Topics
          </Link>
          {" / "}
          <span className="text-text-primary">{topic.shortTitle}</span>
        </nav>

        {/* Header */}
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {topic.title}
        </h1>
        <p className="mt-4 text-lg text-text-secondary">{topic.overview}</p>

        {/* Agencies and codes */}
        <div className="mt-4 flex flex-wrap gap-2">
          {topic.primaryAgencies.map((agency) => (
            <span
              key={agency}
              className="rounded-full bg-accent-surface px-3 py-1 text-xs font-medium text-accent"
            >
              {agency}
            </span>
          ))}
          {topic.primaryCodes.map((code) => (
            <span
              key={code}
              className="rounded-full bg-badge-bg px-3 py-1 text-xs font-medium text-badge-text"
            >
              {code}
            </span>
          ))}
        </div>

        {/* FAQ section */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold text-text-primary">
            Frequently Asked Questions
          </h2>
          <div className="mt-6 space-y-6">
            {topic.faqs.map((faq, i) => (
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

        {/* Related Tools */}
        {(() => {
          const toolKeys = TOPIC_TOOLS[slug] ?? [];
          const toolList = toolKeys
            .map((k) => ALL_TOOLS[k])
            .filter(Boolean);
          if (toolList.length === 0) return null;
          return (
            <section className="mt-10">
              <h2 className="text-lg font-semibold text-text-primary">
                Related Tools
              </h2>
              <p className="mt-2 text-sm text-text-tertiary">
                Free interactive tools for this topic — no AI needed.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {toolList.map((tool) => (
                  <Link
                    key={tool.href}
                    href={tool.href}
                    className="rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface"
                  >
                    <span className="font-medium text-text-primary">
                      {tool.title}
                    </span>
                    <p className="mt-1 text-sm text-text-tertiary">
                      {tool.description}
                    </p>
                  </Link>
                ))}
              </div>
            </section>
          );
        })()}

        {/* CTA */}
        <section className="mt-10 rounded-lg bg-accent-surface p-6 text-center">
          <h2 className="text-lg font-semibold text-text-primary">
            Have a specific question?
          </h2>
          <p className="mt-2 text-text-secondary">
            Ask our AI-powered assistant about your California employment rights.
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-accent-hover"
          >
            Ask Your Question
          </Link>
        </section>

        {/* Related topics */}
        {related.length > 0 && (
          <section className="mt-10">
            <h2 className="text-lg font-semibold text-text-primary">
              Related Topics
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {related.map(
                (r) =>
                  r && (
                    <Link
                      key={r.slug}
                      href={`/topics/${r.slug}`}
                      className="rounded-lg border border-border p-4 transition-colors hover:border-border-hover hover:bg-accent-surface"
                    >
                      <span className="font-medium text-text-primary">
                        {r.shortTitle}
                      </span>
                      <p className="mt-1 text-sm text-text-tertiary">
                        {r.description}
                      </p>
                    </Link>
                  )
              )}
            </div>
          </section>
        )}

        {/* Related claims */}
        {relatedClaims.length > 0 && (
          <section className="mt-10">
            <h2 className="text-lg font-semibold text-text-primary">
              Related Claims
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {relatedClaims.map((rc) => (
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
              ))}
            </div>
          </section>
        )}
      </div>
      </div>
    </>
  );
}
