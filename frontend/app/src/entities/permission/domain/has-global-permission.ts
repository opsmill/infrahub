import { getGlobalPermissionsFromApi } from "@/entities/permission/api/get-global-permissions-from-api";
import { SUPER_ADMIN } from "@/entities/permission/domain/model/permission";

export type HasGlobalPermission = (action: string) => Promise<boolean>;

// A GLOBAL permission's `decision` is the backend `PermissionDecision` (an InfrahubNumberEnum:
// DENY=1, ALLOW_DEFAULT=2, ALLOW_OTHER=4, ALLOW_ALL=6) exposed on a `String!` field, so it arrives
// as the stringified integer (e.g. "6"). A permission is granted for any ALLOW* decision, i.e. not
// DENY. (This differs from OBJECT permissions, whose decision is a string enum name like "ALLOW".)
const GRANTING_GLOBAL_DECISIONS = new Set(["2", "4", "6"]);

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
