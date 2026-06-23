import { useMutation, useQueryClient } from "@tanstack/react-query";

import { addDropdown } from "@/entities/schema/domain/add-dropdown";
import { invalidateSchemaQueries } from "@/entities/schema/ui/queries/invalidate-schema-queries";

export function useAddDropdownMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: addDropdown,
    onSuccess: () => {
      // Adding a dropdown option changes the schema; refresh schema queries
      // so the new option appears immediately (without waiting on the hash poll).
      invalidateSchemaQueries(queryClient);
    },
  });
}
