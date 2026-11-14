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
    // Returning the refetches keeps a save pending until the page shows the saved values.
    onSuccess: (_data, params) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.all() }),
        ("instanceLabel" in params || "instanceColor" in params) &&
          queryClient.invalidateQueries({ queryKey: getConfigQueryOptions().queryKey }),
      ]),
  });
}
