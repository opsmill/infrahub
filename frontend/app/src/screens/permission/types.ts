export type PermissionDecisionData = "ALLOW" | "ALLOW_DEFAULT" | "ALLOW_OTHER" | "DENY";

export type PermissionAction = "view" | "create" | "update" | "delete";

export type PermissionData = Record<PermissionAction, PermissionDecisionData> & { kind: string };

export type PermissionDecision = { isAllowed: true } | { isAllowed: false; message: string };

export type Permission = Record<PermissionAction, PermissionDecision>;
