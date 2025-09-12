import { useRouteError } from "react-router";

import ErrorFallback from "@/shared/components/errors/error-fallback";

export function ErrorBoundaryRouter() {
  const error = useRouteError();

  return <ErrorFallback error={error as Error} onReset={() => window.location.reload()} />;
}
