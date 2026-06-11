import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { PreferenceValues } from "@/entities/preferences/domain/types";
import { upsertMyUserPreference } from "@/entities/preferences/domain/upsert-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function useUpsertMyUserPreferences() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const accountId = auth.user?.id;

  return useMutation({
    mutationFn: (values: PreferenceValues) => {
      if (!accountId) {
        return Promise.reject(
          new Error("Cannot save preferences without an authenticated account")
        );
      }
      // Lazy upsert: no id — the backend resolves or creates the row from the account.
      return upsertMyUserPreference({ accountId, ...values });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.user(accountId) });
    },
  });
}
