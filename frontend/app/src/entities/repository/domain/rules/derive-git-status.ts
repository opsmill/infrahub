export type GitStatus = "loading" | "check-failed" | "inert" | "error" | "neutral";

export interface DeriveGitStatusInput {
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
 * inert state on a request that never settles.
 */
export function deriveGitStatus({
  totalIsPending,
  totalError,
  totalCount,
  failingIsPending,
  failingError,
  failingCount,
}: DeriveGitStatusInput): GitStatus {
  if (totalError) return "check-failed";
  if (totalCount === 0) return "inert";
  if (totalIsPending || failingIsPending) return "loading";
  if (failingError) return "check-failed";
  if (failingCount !== undefined && failingCount > 0) return "error";
  return "neutral";
}
