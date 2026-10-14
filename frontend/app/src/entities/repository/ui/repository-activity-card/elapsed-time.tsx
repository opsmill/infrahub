import React from "react";

import { formatElapsed } from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

const TICK_MS = 1000;

function useNow() {
  const [now, setNow] = React.useState(Date.now);

  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  return now;
}

export function ElapsedTime({ since }: { since: string }) {
  const now = useNow();

  return (
    <span role="timer" className="ml-auto shrink-0 pl-4 text-foreground-muted text-sm tabular-nums">
      <span className="sr-only">Running for </span>
      {formatElapsed(now - new Date(since).getTime())}
    </span>
  );
}
