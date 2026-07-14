/**
 * Shared, dependency-free contract for the outbound `X-Priority` request header.
 *
 * The frontend may only ever emit `'high'` or `'low'`. `'normal'` is the
 * backend's fallback and is deliberately unrepresentable here (data-model,
 * critique E1). Every transport normalizes its per-request value through
 * {@link resolvePriority} before writing the header, so a stray or legacy
 * value cannot leak an out-of-contract priority.
 *
 * ## Opting a request down to `low` (ONE convention, per transport)
 *
 * The default is {@link DEFAULT_PRIORITY} (`'high'`) everywhere — an undeclared
 * request needs no changes and inherits `high`. To opt a single request down to
 * `low`, declare it at the call site using its transport's idiom:
 *
 * - **GraphQL (Apollo)** — pass `context: { priority: 'low' }` on the operation.
 *   The `priorityLink` reads `previousContext.priority` and normalizes it.
 *   ```ts
 *   graphqlClient.query({ query: MY_QUERY, context: { priority: "low" } });
 *   ```
 *
 * - **REST (`openapi-fetch`)** — pre-set the header via `params.header`. The
 *   openapi-fetch `Middleware` `options` object is read-only and exposes no
 *   custom per-request field, so the header (not a bespoke option) is the opt-in
 *   surface; `authMiddleware.onRequest` reads and preserves whatever is present.
 *   ```ts
 *   apiClient.GET("/my/path", { params: { header: { [PRIORITY_HEADER]: "low" } } });
 *   ```
 *
 * - **Raw fetch (`fetchUrl`)** — pass the `{ priority: 'low' }` option argument.
 *   ```ts
 *   fetchUrl(url, payload, { priority: "low" });
 *   ```
 *
 * No helper wraps these idioms: the v1 `low` set is empty (no production caller
 * yet), so a helper would serve only tests — YAGNI (Constitution VII). Each
 * idiom is a single literal and self-explanatory at the call site.
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
