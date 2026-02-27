interface ConversationEndedProps {
  onStartNew: () => void;
}

export default function ConversationEnded({ onStartNew }: ConversationEndedProps) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4 text-center">
      <p className="text-sm text-text-secondary">
        You&apos;ve reached the follow-up limit for this conversation.
      </p>
      <button
        onClick={onStartNew}
        className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white
                   transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2
                   focus:ring-accent/20"
      >
        Start New Conversation
      </button>
    </div>
  );
}
