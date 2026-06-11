import { queryOptions, useQuery } from "@tanstack/react-query";

import { getEffectivePreferences } from "@/entities/preferences/domain/get-effective-preferences";
import { preferencesQueryKeys } from "@/entities/preferences/ui/queries/preferences-query.keys";

export function getEffectivePreferencesQueryOptions() {
  return queryOptions({
    queryKey: preferencesQueryKeys.effective(),
    queryFn: getEffectivePreferences,
  });
}

export function useEffectivePreferences() {
  return useQuery(getEffectivePreferencesQueryOptions());
}
