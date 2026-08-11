import { queryOptions, useQuery } from "@tanstack/react-query";

import { getGlobalPreferences } from "@/entities/preferences/domain/use-cases/get-global-preferences";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences.query-keys";

export function getGlobalPreferencesQueryOptions() {
  return queryOptions({
    queryKey: preferencesQueryKeys.global(),
    queryFn: getGlobalPreferences,
  });
}

export function useGlobalPreferences() {
  return useQuery(getGlobalPreferencesQueryOptions());
}
