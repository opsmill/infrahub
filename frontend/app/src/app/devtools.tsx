import * as React from "react";

export const TanStackQueryDevtools = import.meta.env.VITE_DEVTOOLS
  ? React.lazy(() =>
      import("@tanstack/react-query-devtools").then((module) => ({
        default: module.ReactQueryDevtools,
      }))
    )
  : () => null;

if (import.meta.env.VITE_DEVTOOLS) {
  const { scan } = await import("react-scan");
  scan({ enabled: true });
}
