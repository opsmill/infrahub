import React from "react";

const TICK_MS = 1000;

export function useNow() {
  const [now, setNow] = React.useState(Date.now);

  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  return now;
}
