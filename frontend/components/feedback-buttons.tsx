"use client";

import { useCallback, useState } from "react";
import { submitFeedback } from "@/lib/api";

interface FeedbackButtonsProps {
  queryId: string;
}

export default function FeedbackButtons({ queryId }: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<1 | -1 | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleFeedback = useCallback(
    async (rating: 1 | -1) => {
      setSubmitting(true);
      const ok = await submitFeedback(queryId, rating);
      if (ok) {
        setSubmitted(rating);
      }
      setSubmitting(false);
    },
    [queryId]
  );

  if (submitted !== null) {
    return (
      <p className="text-xs text-text-tertiary">
        {submitted === 1 ? "Thanks for the feedback!" : "Thanks — we'll work on improving."}
      </p>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-tertiary">Was this helpful?</span>
      <button
        onClick={() => handleFeedback(1)}
        disabled={submitting}
        className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded px-2 py-1
                   text-sm text-text-tertiary hover:bg-feedback-hover-up hover:text-feedback-text-up
                   disabled:opacity-50"
        aria-label="Thumbs up"
      >
        👍
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        disabled={submitting}
        className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded px-2 py-1
                   text-sm text-text-tertiary hover:bg-feedback-hover-down hover:text-feedback-text-down
                   disabled:opacity-50"
        aria-label="Thumbs down"
      >
        👎
      </button>
    </div>
  );
}
