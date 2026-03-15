export default function AuthLoading({
  message = "Checking sign-in...",
}: {
  message?: string;
}) {
  return (
    <div className="flex flex-1 items-center justify-center" role="status">
      <div className="flex flex-col items-center gap-3">
        <svg
          className="h-6 w-6 animate-spin text-accent"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm text-text-tertiary">{message}</p>
      </div>
    </div>
  );
}
