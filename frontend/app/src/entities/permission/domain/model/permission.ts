export const ACCOUNT_PERMISSION_OBJECT = "CoreBasePermission";
export const GLOBAL_PERMISSION_OBJECT = "CoreGlobalPermission";
export const OBJECT_PERMISSION_OBJECT = "CoreObjectPermission";

export const MANAGE_GLOBAL_PREFERENCES = "manage_global_preferences";

/** Super-admin grant bypasses every other global permission check. */
export const SUPER_ADMIN = "super_admin";

export type PermissionDecisionData = "ALLOW" | "ALLOW_DEFAULT" | "ALLOW_OTHER" | "DENY";

// GLOBAL decision is a stringified InfrahubNumberEnum (DENY=1, ALLOW_DEFAULT=2, ALLOW_OTHER=4, ALLOW_ALL=6) — unlike OBJECT perms, which use string names.
export const GLOBAL_PERMISSION_DECISION = {
  DENY: "1",
  ALLOW_DEFAULT: "2",
  ALLOW_OTHER: "4",
  ALLOW_ALL: "6",
} as const;

/** A single account-wide permission edge: an action paired with its resolved decision. */
export interface GlobalPermission {
  action: string;
  decision: string;
}

export type PermissionAction = "view" | "create" | "update" | "delete";

export type PermissionData = Record<PermissionAction, PermissionDecisionData> & { kind: string };

export type PermissionDecision =
  | { isAllowed: true; message?: string }
  | { isAllowed: false; message: string };

export type Permission = Record<PermissionAction, PermissionDecision>;

export const PERMISSION_ALLOW_ALL: Permission = {
  create: { isAllowed: true },
  view: { isAllowed: true },
  update: { isAllowed: true },
  delete: { isAllowed: true },
};

export const PERMISSION_DENY_ALL: Permission = {
  create: { isAllowed: false, message: "Loading permissions..." },
  view: { isAllowed: false, message: "Loading permissions..." },
  update: { isAllowed: false, message: "Loading permissions..." },
  delete: { isAllowed: false, message: "Loading permissions..." },
};
