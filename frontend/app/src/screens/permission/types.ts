export type PermissionDecisionData = "DENY" | "ALLOW_ALL" | "ALLOW_DEFAULT" | "ALLOW_OTHER";

export type PermissionAction = "view" | "create" | "update" | "delete";

export type PermissionData = Record<PermissionAction, PermissionDecisionData> & { kind: string };

export type PermissionDecision = { isAllowed: true } | { isAllowed: false; message: string };

export type Permission = Record<PermissionAction, PermissionDecision>;
