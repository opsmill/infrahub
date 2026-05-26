import { useMutation, useQueryClient } from "@tanstack/react-query";

import { addEnum } from "@/entities/schema/domain/add-enum";
import { invalidateSchemaQueries } from "@/entities/schema/ui/queries/invalidate-schema-queries";

export function useAddEnumMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: addEnum,
    onSuccess: () => {
      // Adding an enum value changes the schema; refresh schema queries so the
      // new value appears immediately (without waiting on the hash poll).
      invalidateSchemaQueries(queryClient);
    },
  });
}
