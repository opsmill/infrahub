import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import {
  GLOBAL_PERMISSION_DECISION,
  type GlobalPermission,
  SUPER_ADMIN,
} from "@/entities/permission/domain/model/permission";

export type HasGlobalPermission = (action: string) => Promise<boolean>;

// Mirrors the backend PermissionManager.has_permission: resolve(action) OR super_admin.
export const hasGlobalPermission: HasGlobalPermission = async (action) => {
  const { data } = await getGlobalPermissionsFromApi();
  const permissions = (data.InfrahubPermissions.global_permissions?.edges ?? []).map(
    (edge) => edge.node
  );

  return resolve(permissions, action) || resolve(permissions, SUPER_ADMIN);
};

function resolve(permissions: GlobalPermission[], action: string): boolean {
  let granted = false;

  for (const permission of permissions) {
    if (permission.action !== action) continue;
    if (permission.decision === GLOBAL_PERMISSION_DECISION.DENY) return false;
    granted = true;
  }

  return granted;
}
