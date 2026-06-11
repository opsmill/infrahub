import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { resetMyUserPreference } from "@/entities/preferences/domain/reset-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function useResetMyUserPreferences() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const accountId = auth.user?.id;

  return useMutation({
    mutationFn: resetMyUserPreference,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.effective() });
      queryClient.invalidateQueries({ queryKey: preferencesQueryKeys.user(accountId) });
    },
  });
}
