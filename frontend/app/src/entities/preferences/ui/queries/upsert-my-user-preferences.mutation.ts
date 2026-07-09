import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { UpsertMyUserPreferenceParams } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";
import { upsertMyUserPreference } from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

/** Write the caller's own row, then invalidate the effective-preferences query. */
export function useUpdateMyUserPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpsertMyUserPreferenceParams) => upsertMyUserPreference(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
    },
  });
}
