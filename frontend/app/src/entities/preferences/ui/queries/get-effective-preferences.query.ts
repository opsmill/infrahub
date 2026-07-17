import { queryOptions, useQuery } from "@tanstack/react-query";

import { getEffectivePreferences } from "@/entities/preferences/domain/use-cases/get-effective-preferences";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";

export function getEffectivePreferencesQueryOptions() {
  return queryOptions({
    queryKey: preferencesQueryKeys.effective(),
    queryFn: getEffectivePreferences,
  });
}

export function useGetEffectivePreferences(options?: { enabled?: boolean }) {
  // Authenticated query: callers gate it with `enabled` so it never fires pre-auth (e.g. the login
  // page), where a 401 trips Apollo's error link and bounces back to /login.
  return useQuery({ ...getEffectivePreferencesQueryOptions(), ...options });
}
