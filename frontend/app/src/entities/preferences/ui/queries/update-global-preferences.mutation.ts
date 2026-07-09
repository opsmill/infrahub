import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

/**
 * Update the org-wide defaults. Invalidates both the effective-preferences query (a changed org
 * default can move a user's resolved value/source) and the raw GLOBAL query the card reads from.
 */
export function useUpdateGlobalPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateGlobalPreference,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.global() });
    },
  });
}
