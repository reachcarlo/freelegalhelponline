import { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllTopicSlugs, getTopicBySlug, topics } from "@/lib/topics";

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
      </div>
      </div>
    </>
  );
}
