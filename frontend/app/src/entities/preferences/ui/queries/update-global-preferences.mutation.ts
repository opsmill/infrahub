import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type UpdateGlobalPreferenceParams,
  updateGlobalPreference,
} from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

/** Invalidates the effective query too: a changed org default can move a user's resolved value/source. */
export function useUpdateGlobalPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    // Wrap so mutationFn gets only `params`; react-query passes extra positionals to a bare ref.
    mutationFn: (params: UpdateGlobalPreferenceParams) => updateGlobalPreference(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.global() });
    },
  });
}
