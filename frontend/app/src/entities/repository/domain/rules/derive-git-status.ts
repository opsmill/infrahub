/**
 * The five states the Git status indicator can display.
 *
 * Closed on purpose: only the import-error sync status is distinguished, and every other
 * status value is neutral. A third status treatment would contradict the feature's spec.
 */
export type GitStatus = "loading" | "check-failed" | "inert" | "error" | "neutral";

/**
 * Both lookups' query lifecycle, flattened.
 *
 * `isPending` — never `isFetching`. With a refresh interval, `isFetching` is true on every
 * poll while `isPending` is true only until data first arrives, so reading the wrong one makes
 * the indicator flash its loading treatment every ten seconds.
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
 * The order of these checks is the substance of the rule, not an implementation detail:
 *
 * 1. Never present a state that has not been confirmed. A glyph that flashes neutral before
 *    turning red reads as a glitch and trains operators to distrust it.
 * 2. Without the total, nothing is known. This is also the path a permission error takes,
 *    since the underlying query surfaces every failure the same way.
 * 3. A branch with no repositories cannot have failing ones — the failing count is a subset of
 *    an empty set. So the total settles the answer, and a failed failing-lookup is irrelevant
 *    rather than alarming. This check must stay above the one below it.
 * 4. With repositories present, a failed failing-lookup leaves health genuinely unknown.
 *    Neither "healthy" nor "failing" is a fact in hand, so neither may be claimed.
 */
export function deriveGitStatus({
  totalIsPending,
  totalError,
  totalCount,
  failingIsPending,
  failingError,
  failingCount,
}: DeriveGitStatusInput): GitStatus {
  if (totalIsPending || failingIsPending) return "loading";
  if (totalError) return "check-failed";
  if (totalCount === 0) return "inert";
  if (failingError) return "check-failed";
  if (failingCount !== undefined && failingCount > 0) return "error";
  return "neutral";
}
