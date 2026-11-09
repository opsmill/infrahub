import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type UpdateGlobalPreferenceParams,
  updateGlobalPreference,
} from "@/entities/preferences/domain/use-cases/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";

export function useUpdateGlobalPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpdateGlobalPreferenceParams) => updateGlobalPreference(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.all() });
    },
  });
}
