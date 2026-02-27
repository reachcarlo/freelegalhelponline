"use client";

interface LoadingBarProps {
  active: boolean;
}

export default function LoadingBar({ active }: LoadingBarProps) {
  if (!active) return null;

  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-border">
      <div className="h-full w-1/3 animate-loading-bar rounded-full bg-accent" />
    </div>
  );
}
