import { queryOptions, useQuery } from "@tanstack/react-query";

import { getGlobalPreference } from "@/entities/preferences/domain/get-global-preference";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function getGlobalPreferencesQueryOptions() {
  return queryOptions({
    queryKey: preferencesQueryKeys.global(),
    queryFn: getGlobalPreference,
  });
}

export function useGlobalPreferences() {
  return useQuery(getGlobalPreferencesQueryOptions());
}
