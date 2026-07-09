import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { useGlobalPermission } from "@/entities/permission/ui/queries/use-global-permission";

/** Gates the "Organisation defaults" tab on the `manage_global_preferences` permission. */
export function useCanManageGlobalPreferences() {
  return useGlobalPermission(MANAGE_GLOBAL_PREFERENCES);
}
