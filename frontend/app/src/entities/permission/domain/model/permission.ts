export type PermissionDecisionData = "ALLOW" | "ALLOW_DEFAULT" | "ALLOW_OTHER" | "DENY";

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
