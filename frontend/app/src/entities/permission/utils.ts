import { warnUnexpectedType } from "@/shared/utils/common";

import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";
import type {
  Permission,
  PermissionAction,
  PermissionData,
  PermissionDecision,
  PermissionDecisionData,
} from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

import { PERMISSION_ALLOW_ALL } from "./constants";

export interface GetPermissionOptions {
  branch?: { status: BranchStatus };
  schema: ModelSchema;
}

const getMessage = (action: string, decision?: PermissionDecisionData): string => {
  if (!decision)
    return `Unable to determine permission to ${action} this object. Please contact your administrator.`;

  switch (decision) {
    case "DENY":
      return `You don't have permission to ${action} this object.`;
    case "ALLOW_DEFAULT":
      return `This action is only allowed on the default branch. Please switch to the default branch to ${action} this object.`;
    case "ALLOW_OTHER":
      return `This action is not allowed on the default branch. Please switch to a different branch to ${action} this object.`;
    case "ALLOW":
      return `You have permission to ${action} this object on any branch.`;
    default:
      warnUnexpectedType(decision);
      return "";
  }
};

function applyBranchOverride(permission: Permission, options?: GetPermissionOptions): Permission {
  if (options?.branch?.status === BRANCH_STATUS.MERGED && options?.schema?.branch !== "agnostic") {
    const mergedDenial: PermissionDecision = {
      isAllowed: false,
      message: "Cannot edit objects on a merged branch",
    };
    return {
      view: permission.view,
      create: mergedDenial,
      update: mergedDenial,
      delete: mergedDenial,
    };
  }
  return permission;
}

export function getPermission(
  permission?: Array<{ node: PermissionData }>,
  options?: GetPermissionOptions
): Permission {
  if (!Array.isArray(permission)) return applyBranchOverride(PERMISSION_ALLOW_ALL, options);

  const createPermissionAction = (action: PermissionAction): PermissionDecision => {
    const permissionAllowNode = permission.find(({ node }) => node[action] === "ALLOW");

    if (permissionAllowNode) {
      return { isAllowed: true };
    }

    const permissionDeniedNode = permission.find(({ node }) => node[action] !== "ALLOW");

    return {
      isAllowed: false,
      message: getMessage(action, permissionDeniedNode?.node?.[action]),
    };
  };

  const basePermission: Permission = {
    view: createPermissionAction("view"),
    create: createPermissionAction("create"),
    update: createPermissionAction("update"),
    delete: createPermissionAction("delete"),
  };

  return applyBranchOverride(basePermission, options);
}
