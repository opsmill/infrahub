import type { FallbackProps } from "react-error-boundary";

import ErrorFallback from "@/shared/components/errors/error-fallback";

export const ErrorBoundaryApp = ({ error, resetErrorBoundary }: FallbackProps) => {
  return <ErrorFallback error={error} onReset={resetErrorBoundary} />;
};
