// A Date keeps milliseconds, so the instant one millisecond before the end is the last one the license covers.
const ONE_MILLISECOND_MS = 1;

/** Returns an instant on the last day a license covers, given `ends_at`, the first instant it no longer covers. */
export function lastCoveredDay(endsAt: string): Date {
  return new Date(new Date(endsAt).getTime() - ONE_MILLISECOND_MS);
}
