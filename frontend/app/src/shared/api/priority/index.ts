// The `X-Priority` request header value. The frontend only sends `high` or `low`;
// the backend uses it to prioritize requests under load.
export type RequestPriority = "high" | "low";

export const DEFAULT_PRIORITY: RequestPriority = "high";

export const PRIORITY_HEADER = "X-Priority";

// Coerce any runtime value to a valid priority: `low` only for exactly "low", anything else to `high`.
export function resolvePriority(value: unknown): RequestPriority {
  return value === "low" ? "low" : DEFAULT_PRIORITY;
}
