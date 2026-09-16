/**
 * The five states the Git status indicator can display. Only the import-error sync status
 * counts as a failure; every other status is neutral.
 */
export type GitStatus = "loading" | "check-failed" | "inert" | "error" | "neutral";

/**
 * Both lookups' outcomes, flattened.
 *
 * A pending flag must mean "no value has arrived yet" — not "a value is being refreshed" — and
 * a count must be absent while its lookup is pending rather than standing in as a placeholder.
 * A count of zero is therefore always a real answer.
 */
export interface DeriveGitStatusInput {
  totalIsPending: boolean;
  totalError: Error | null;
  totalCount: number | undefined;
  failingIsPending: boolean;
  failingError: Error | null;
  failingCount: number | undefined;
}

/**
 * Folds the two repository counts into one display state.
 *
 * The order of the checks carries the meaning:
 *
 * - Without a total, nothing is known, so the check is reported as failed rather than healthy.
 * - A total of zero settles the question on its own: no repositories means none failing, so
 *   the other lookup cannot change the answer and is not waited for.
 * - Otherwise nothing is claimed until both lookups have produced a value, and a failure to
 *   obtain the failing count is reported as unknown rather than as healthy.
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
