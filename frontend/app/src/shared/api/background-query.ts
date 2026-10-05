import type { QueryStatus } from "@tanstack/react-query";

import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode, isThrownShed } from "@/shared/api/graphql/error-handling";

const BACKGROUND_QUERY_MAX_RETRIES = 2;

/**
 * Retry policy for a query that refreshes a card in the background. A denial can't succeed on a
 * retry, and the transport has already retried a shed request as far as the load allows, so
 * neither is retried here. Anything else gets a couple of retries with the default backoff.
 */
export function retryBackgroundQuery(failureCount: number, error: Error): boolean {
  return (
    failureCount < BACKGROUND_QUERY_MAX_RETRIES &&
    !hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED) &&
    !isThrownShed(error)
  );
}

// After a failure the poll slows down instead of stopping, so a card that kept its last rows
// catches up on its own once the backend recovers; a denial can't recover, so it stops.
const FAILED_POLL_SLOWDOWN = 6;

export function pollWhileHealthy(
  isActive: boolean,
  intervalMs: number,
  query: { state: { status: QueryStatus; error: Error | null } }
): number | false {
  if (!isActive) return false;
  if (query.state.status !== "error") return intervalMs;
  const { error } = query.state;
  if (error && hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)) return false;
  return intervalMs * FAILED_POLL_SLOWDOWN;
}
