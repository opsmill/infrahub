import ErrorFallback from "@/shared/components/errors/error-fallback";
import { FallbackProps } from "react-error-boundary";

export const ErrorBoundaryApp = ({ error, resetErrorBoundary }: FallbackProps) => {
  return <ErrorFallback error={error} onReset={resetErrorBoundary} />;
};
