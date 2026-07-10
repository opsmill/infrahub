import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import {
  GRANTING_GLOBAL_DECISIONS,
  SUPER_ADMIN,
} from "@/entities/permission/domain/model/permission";

export type HasGlobalPermission = (action: string) => Promise<boolean>;

// A super_admin grant satisfies ANY action, mirroring backend enforcement.
export const hasGlobalPermission: HasGlobalPermission = async (action) => {
  const { data } = await getGlobalPermissionsFromApi();
  const edges = data.InfrahubPermissions.global_permissions?.edges ?? [];

  return edges.some(
    ({ node }) =>
      (node.action === action || node.action === SUPER_ADMIN) &&
      GRANTING_GLOBAL_DECISIONS.has(node.decision)
  );
};
