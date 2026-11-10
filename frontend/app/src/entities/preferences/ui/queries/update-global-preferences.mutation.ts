import { useMutation, useQueryClient } from "@tanstack/react-query";

import { getConfigQueryOptions } from "@/entities/config/ui/queries/get-config.query";
import {
  type UpdateGlobalPreferenceParams,
  updateGlobalPreference,
} from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";

export function useUpdateGlobalPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpdateGlobalPreferenceParams) => updateGlobalPreference(params),
    // Returning the refetches makes a save resolve only once the forms compare against the saved values.
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.all() }),
        queryClient.invalidateQueries({ queryKey: getConfigQueryOptions().queryKey }),
      ]),
  });
}
