import { hashKey, type QueryClient } from "@tanstack/react-query";

import { getConfigQueryOptions } from "@/entities/config/ui/queries/get-config.query";

/**
 * Removes the previous session's cached queries and mutations.
 *
 * The public config, the same for every user, is kept because its reader stays on screen through a login or logout
 * without re-rendering, so it would keep reading a removed entry that no later refetch updates.
 */
export function clearSessionCache(queryClient: QueryClient) {
  const configQueryHash = hashKey(getConfigQueryOptions().queryKey);
  queryClient.getMutationCache().clear();
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== configQueryHash });
}
