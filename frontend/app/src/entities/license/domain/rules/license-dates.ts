const ONE_SECOND_MS = 1000;

/** Returns an instant on the last day a license covers, given `ends_at`, the first instant it no longer covers. */
export function lastCoveredDay(endsAt: string): Date {
  return new Date(new Date(endsAt).getTime() - ONE_SECOND_MS);
}

export function dayCount(count: number): string {
  return `${count} ${count === 1 ? "day" : "days"}`;
}
