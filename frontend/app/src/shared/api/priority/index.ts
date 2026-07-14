/**
 * Shared, dependency-free contract for the outbound `X-Priority` request header.
 *
 * The frontend may only ever emit `'high'` or `'low'`. `'normal'` is the
 * backend's fallback and is deliberately unrepresentable here (data-model,
 * critique E1). Every transport normalizes its per-request value through
 * {@link resolvePriority} before writing the header, so a stray or legacy
 * value cannot leak an out-of-contract priority.
 */

export type RequestPriority = "high" | "low";

export const DEFAULT_PRIORITY: RequestPriority = "high";

export const PRIORITY_HEADER = "X-Priority";

/**
 * Coerce an untyped runtime value into a {@link RequestPriority}.
 *
 * Returns `'low'` only for exactly `'low'`; everything else (including
 * `'normal'`, `undefined`, and non-string values) resolves to
 * {@link DEFAULT_PRIORITY} (`'high'`).
 */
export function resolvePriority(value: unknown): RequestPriority {
  return value === "low" ? "low" : DEFAULT_PRIORITY;
}
