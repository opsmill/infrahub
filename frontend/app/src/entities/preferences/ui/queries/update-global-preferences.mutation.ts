import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

/**
 * Updates the organisation-wide singleton via `InfrahubGlobalPreferenceUpdate`.
 * Invalidates the effective-preferences query on success.
 */
export function useUpdateGlobalPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateGlobalPreference,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
    },
  });
}
