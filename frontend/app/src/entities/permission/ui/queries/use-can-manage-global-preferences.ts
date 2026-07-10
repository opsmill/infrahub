import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { useGlobalPermission } from "@/entities/permission/ui/queries/use-global-permission";

export function useCanManageGlobalPreferences() {
  return useGlobalPermission(MANAGE_GLOBAL_PREFERENCES);
}
