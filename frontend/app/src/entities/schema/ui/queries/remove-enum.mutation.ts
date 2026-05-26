import { useMutation, useQueryClient } from "@tanstack/react-query";

import { removeEnum } from "@/entities/schema/domain/remove-enum";
import { invalidateSchemaQueries } from "@/entities/schema/ui/queries/invalidate-schema-queries";

export function useRemoveEnumMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: removeEnum,
    onSuccess: () => {
      // Removing an enum value changes the schema; refresh schema queries.
      invalidateSchemaQueries(queryClient);
    },
  });
}
