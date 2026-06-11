import { queryOptions, useQuery } from "@tanstack/react-query";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { getMyUserPreference } from "@/entities/preferences/domain/get-my-user-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function getMyUserPreferencesQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: preferencesQueryKeys.user(accountId),
    queryFn: () => getMyUserPreference({ accountId }),
  });
}

export function useMyUserPreferences() {
  const auth = useAuth();
  const accountId = auth.user?.id;

  return useQuery({
    ...getMyUserPreferencesQueryOptions(accountId ?? ""),
    enabled: !!accountId,
  });
}
