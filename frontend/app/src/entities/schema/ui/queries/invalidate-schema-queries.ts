import type { QueryClient } from "@tanstack/react-query";

/**
 * Schema queries don't share a single canonical queryKey prefix:
 *
 * - `loadSchemaQueryOptions` keys queries as `[schemaHash, "schema"]`
 * - `getSchemaHashQueryOptions` keys queries as `[branchName, atDate, "schema", "hash"]`
 *
 * Both contain the literal `"schema"` somewhere in their key, so we invalidate
 * by predicate. Used by every schema mutation (add/remove dropdown/enum) to
 * surface schema changes immediately instead of waiting on the hash poll.
 */
export function invalidateSchemaQueries(queryClient: QueryClient) {
  queryClient.invalidateQueries({
    predicate: (query) => query.queryKey.includes("schema"),
  });
}
