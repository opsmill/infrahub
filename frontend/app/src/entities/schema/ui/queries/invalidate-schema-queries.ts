import type { QueryClient } from "@tanstack/react-query";

import { schemaQueryKeys } from "@/entities/schema/ui/queries/schema.query-keys";

/**
 * Invalidate every schema-related query (hash + load) so a mutation that
 * changes the schema (add/remove dropdown/enum) surfaces immediately instead
 * of waiting for the schema-hash poll to detect the drift.
 *
 * All schema queries share the `schemaQueryKeys.all` (`["schema"]`) prefix —
 * invalidating that one key covers the whole entity.
 */
export function invalidateSchemaQueries(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: schemaQueryKeys.all });
}
