import { useMutation, useQueryClient } from "@tanstack/react-query";

import { removeDropdown } from "@/entities/schema/domain/remove-dropdown";
import { invalidateSchemaQueries } from "@/entities/schema/ui/queries/invalidate-schema-queries";

export function useRemoveDropdownMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: removeDropdown,
    onSuccess: () => {
      // Removing a dropdown option changes the schema; refresh schema queries.
      invalidateSchemaQueries(queryClient);
    },
  });
}
