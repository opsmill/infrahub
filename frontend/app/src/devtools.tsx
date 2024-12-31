import * as React from "react";

export const TanStackQueryDevtools = import.meta.env.VITE_DEVTOOLS
  ? React.lazy(() =>
      import("@tanstack/react-query-devtools").then((module) => ({
        default: module.ReactQueryDevtools,
      }))
    )
  : () => null;
