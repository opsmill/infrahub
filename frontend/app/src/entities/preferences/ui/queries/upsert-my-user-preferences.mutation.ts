import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type UpsertMyUserPreferenceParams,
  upsertMyUserPreference,
} from "@/entities/preferences/domain/use-cases/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function useUpdateMyUserPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    // Wrap so mutationFn gets only `params`; react-query passes extra positionals to a bare ref.
    mutationFn: (params: UpsertMyUserPreferenceParams) => upsertMyUserPreference(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
    },
  });
}
