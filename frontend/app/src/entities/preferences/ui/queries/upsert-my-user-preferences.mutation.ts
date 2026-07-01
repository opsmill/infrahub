import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { UpsertMyUserPreferenceParams } from "@/entities/preferences/domain/upsert-my-user-preference";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

/**
 * Writes the caller's own preference row via `InfrahubSetPreferences(scope: USER)`.
 * Pass explicit `null` for a field to reset it to the global default; omit a
 * field to leave it unchanged. Invalidates the effective-preferences query.
 */
export function useUpdateMyUserPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpsertMyUserPreferenceParams) => upsertMyUserPreference(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
    },
  });
}
