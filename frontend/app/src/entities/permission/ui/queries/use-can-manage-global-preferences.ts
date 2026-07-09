import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { useGlobalPermission } from "@/entities/permission/ui/queries/use-global-permission";

/**
 * Whether the current account may manage the organisation-wide preferences, i.e. holds the
 * `manage_global_preferences` GLOBAL permission. Used to show/hide the "Organisation defaults" tab.
 */
export function useCanManageGlobalPreferences() {
  return useGlobalPermission(MANAGE_GLOBAL_PREFERENCES);
}
