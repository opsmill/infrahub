import { BRANCH_STATUS, type BranchStatus } from "@/entities/branches/constants";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";
import type {
  Permission,
  PermissionAction,
  PermissionData,
  PermissionDecision,
  PermissionDecisionData,
} from "@/entities/permission/types";

export interface GetPermissionOptions {
  branch?: { status: BranchStatus };
}

const getMessage = (action: string, decision?: PermissionDecisionData): string => {
  switch (decision) {
    case "DENY":
      return `You don't have permission to ${action} this object.`;
    case "ALLOW_DEFAULT":
      return `This action is only allowed on the default branch. Please switch to the default branch to ${action} this object.`;
    case "ALLOW_OTHER":
      return `This action is not allowed on the default branch. Please switch to a different branch to ${action} this object.`;
    default:
      return `Unable to determine permission to ${action} this object. Please contact your administrator.`;
  }
};

function getPermissionWithBranchStatus(
  permission: Permission,
  options?: GetPermissionOptions
): Permission {
  if (options?.branch?.status === BRANCH_STATUS.MERGED) {
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
  if (!Array.isArray(permission)) {
    return getPermissionWithBranchStatus(PERMISSION_ALLOW_ALL, options);
  }

  const createPermissionAction = (action: PermissionAction): PermissionDecision => {
    if (permission.some(({ node }) => node[action] === "ALLOW")) {
      return { isAllowed: true };
    }

    return {
      isAllowed: false,
      message: getMessage(action, permission[0]?.node?.[action]),
    };
  };

  const basePermission: Permission = {
    view: createPermissionAction("view"),
    create: createPermissionAction("create"),
    update: createPermissionAction("update"),
    delete: createPermissionAction("delete"),
  };

  return getPermissionWithBranchStatus(basePermission, options);
}
