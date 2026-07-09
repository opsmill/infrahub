import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import {
  GRANTING_GLOBAL_DECISIONS,
  SUPER_ADMIN,
} from "@/entities/permission/domain/model/permission";

export type HasGlobalPermission = (action: string) => Promise<boolean>;

/**
 * Whether the calling account holds a given account-wide permission `action`.
 *
 * A global permission is "held" when the caller's `global_permissions` list contains an edge for
 * that `action` with a granting (non-DENY) decision.
 *
 * A `super_admin` grant satisfies ANY action — mirroring the backend, where
 * `has_permission(action) == resolve_global_permission(action) or is_super_admin()` — so the UI
 * gate matches server-side enforcement even when the specific action isn't explicitly assigned.
 */
export const hasGlobalPermission: HasGlobalPermission = async (action) => {
  const { data } = await getGlobalPermissionsFromApi();
  const edges = data.InfrahubPermissions.global_permissions?.edges ?? [];

  return edges.some(
    ({ node }) =>
      (node.action === action || node.action === SUPER_ADMIN) &&
      GRANTING_GLOBAL_DECISIONS.has(node.decision)
  );
};
