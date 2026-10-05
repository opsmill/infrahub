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

/**
 * Polls while `isActive`, and stops once a fetch has failed through its retries: the card shows its
 * error state, and the next fetch comes from a refresh, a remount or the window regaining focus.
 */
export function pollWhileHealthy(
  isActive: boolean,
  intervalMs: number,
  query: { state: { status: QueryStatus } }
): number | false {
  return isActive && query.state.status !== "error" ? intervalMs : false;
}
