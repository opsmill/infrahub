import ErrorFallback from "@/shared/components/errors/error-fallback";
import { ErrorBoundaryProps } from "react-error-boundary";

export const ErrorBoundaryApp: ErrorBoundaryProps["FallbackComponent"] = ({
  error,
  resetErrorBoundary,
}) => {
  return <ErrorFallback error={error} onReset={resetErrorBoundary} />;
};
