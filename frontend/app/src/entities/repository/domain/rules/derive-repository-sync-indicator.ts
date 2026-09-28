export type RepositorySyncIndicator =
  | "loading"
  | "check-failed"
  | "no-repositories"
  | "failing"
  | "in-sync";

export interface DeriveRepositorySyncIndicatorInput {
  totalIsPending: boolean;
  totalError: Error | null;
  totalCount: number | undefined;
  failingIsPending: boolean;
  failingError: Error | null;
  failingCount: number | undefined;
}

/**
 * A zero total is checked before the pending guard because no repositories means none
 * failing: the second lookup cannot change that answer, and waiting for it would hang the
 * no-repositories state on a request that never settles.
 */
export function deriveRepositorySyncIndicator({
  totalIsPending,
  totalError,
  totalCount,
  failingIsPending,
  failingError,
  failingCount,
}: DeriveRepositorySyncIndicatorInput): RepositorySyncIndicator {
  if (totalError) return "check-failed";
  if (totalCount === 0) return "no-repositories";
  if (totalIsPending || failingIsPending) return "loading";
  if (failingError) return "check-failed";
  if (failingCount !== undefined && failingCount > 0) return "failing";
  return "in-sync";
}
