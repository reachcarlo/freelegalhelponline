import Link from "next/link";
import QuestionPanel from "@/components/question-panel";
import { topics } from "@/lib/topics";

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
      {/* Hero */}
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Free Legal Help
        </h1>
        <p className="mt-3 text-lg text-text-secondary">
          California Employment Rights — Answered by AI
        </p>
        <p className="mt-2 text-sm text-text-tertiary">
          Ask questions about wages, discrimination, retaliation, leave,
          unemployment insurance, and other California workplace protections.
        </p>
      </div>

      {/* Q&A Panel */}
      <QuestionPanel />

      {/* Topic links */}
      <section className="mt-14">
        <h2 className="text-center text-lg font-semibold text-text-primary">
          Browse by Topic
        </h2>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {topics.map((topic) => (
            <Link
              key={topic.slug}
              href={`/topics/${topic.slug}`}
              className="rounded-full border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-hover hover:bg-accent-surface hover:text-accent"
            >
              {topic.shortTitle}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
