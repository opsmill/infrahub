import React from "react";

const TICK_MS = 1000;

function useNow() {
  const [now, setNow] = React.useState(Date.now);

  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  return now;
}

/** "45s", "1m 04s", "2h 05m": the unit that matters for a run of that length. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");

  if (hours > 0) return `${hours}h ${pad(minutes)}m`;
  if (minutes > 0) return `${minutes}m ${pad(seconds)}s`;
  return `${seconds}s`;
}

export function ElapsedTime({ since }: { since: string }) {
  const now = useNow();

  return (
    <span className="ml-auto shrink-0 pl-4 text-foreground-muted text-sm tabular-nums">
      <span className="sr-only">Running for </span>
      {formatElapsed(now - new Date(since).getTime())}
    </span>
  );
}
