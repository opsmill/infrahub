import { queryOptions, useQuery } from "@tanstack/react-query";

import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";

export function canManageGlobalPreferencesQueryOptions() {
  return queryOptions({
    queryKey: ["permissions", "global", MANAGE_GLOBAL_PREFERENCES],
    queryFn: () => hasGlobalPermission(MANAGE_GLOBAL_PREFERENCES),
  });
}

/**
 * Whether the current account may manage the organisation-wide preferences, i.e.
 * holds the `manage_global_preferences` GLOBAL permission. Gates the
 * "Organisation defaults" tab and its editor.
 */
export function useCanManageGlobalPreferences() {
  return useQuery(canManageGlobalPreferencesQueryOptions());
}
