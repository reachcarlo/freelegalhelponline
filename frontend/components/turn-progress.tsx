interface TurnProgressProps {
  currentTurn: number;
  maxTurns: number;
  isStreaming: boolean;
}

export default function TurnProgress({
  currentTurn,
  maxTurns,
  isStreaming,
}: TurnProgressProps) {
  // Only show after the first turn is submitted
  if (currentTurn <= 1 && !isStreaming) return null;

  const displayTurn = isStreaming ? currentTurn : currentTurn - 1;

  return (
    <div className="flex items-center gap-2 text-xs text-text-tertiary">
      <span>
        Turn {displayTurn} of {maxTurns}
      </span>
      <div className="flex gap-1">
        {Array.from({ length: maxTurns }, (_, i) => {
          const turnIndex = i + 1;
          let colorClass: string;

          if (turnIndex < displayTurn) {
            // Completed turns
            colorClass = "bg-accent";
          } else if (turnIndex === displayTurn) {
            // Current turn
            colorClass = "bg-accent/50";
          } else {
            // Future turns
            colorClass = "border border-border bg-transparent";
          }

          return (
            <div
              key={i}
              className={`h-2 w-2 rounded-full ${colorClass}`}
            />
          );
        })}
      </div>
    </div>
  );
}
