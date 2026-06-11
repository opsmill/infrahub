import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateGlobalPreference } from "@/entities/preferences/domain/update-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

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
