import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type UpsertUserPreferencesParams,
  upsertUserPreferences,
} from "@/entities/preferences/domain/use-cases/upsert-user-preferences";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";

export function useUpdateUserPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpsertUserPreferencesParams) => upsertUserPreferences(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
    },
  });
}
