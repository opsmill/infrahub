import { queryOptions, useQuery } from "@tanstack/react-query";

import { getGlobalPreferences } from "@/entities/preferences/domain/use-cases/get-global-preferences";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function getGlobalPreferencesQueryOptions() {
  return queryOptions({
    queryKey: preferencesQueryKeys.global(),
    queryFn: getGlobalPreferences,
  });
}

/**
 * Raw org defaults (scope GLOBAL). Loaded only by the org-defaults card when its tab opens, so a
 * regular user never issues the gated GLOBAL-scope request.
 */
export function useGlobalPreferences() {
  return useQuery(getGlobalPreferencesQueryOptions());
}
