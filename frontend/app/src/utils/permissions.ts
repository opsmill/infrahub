import { Branch } from "@/generated/graphql";
import {
  Permission,
  PermissionAction,
  PermissionData,
  PermissionDecision,
  PermissionDecisionData,
} from "@/screens/role-management/types";
import { store } from "@/state";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { configState } from "@/state/atoms/config.atom";
import { warnUnexpectedType } from "./common";

const isActionAllowedOnBranch = (
  decision: PermissionDecisionData,
  isOnDefaultBranch: boolean
): boolean => {
  switch (decision) {
    case "ALLOW_ALL":
      return true;
    case "ALLOW_DEFAULT":
      return isOnDefaultBranch;
    case "ALLOW_OTHER":
      return !isOnDefaultBranch;
    default:
      return false;
  }
};

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
    case "ALLOW_ALL":
      return `You have permission to ${action} this object on any branch.`;
    default:
      warnUnexpectedType(decision);
      return "";
  }
};

export function getPermission(permission?: Array<{ node: PermissionData }>): Permission {
  if (!permission) return PERMISSION_ALLOW_ALL;

  const config = store.get(configState);
  const currentBranch = store.get(currentBranchAtom);
  const isOnDefaultBranch = !!currentBranch?.is_default;

  const createPermissionAction = (action: PermissionAction): PermissionDecision => {
    if (action === "view" && config?.main.allow_anonymous_access) return { isAllowed: true };

    const permissionAllowNode = permission.find(({ node }) =>
      isActionAllowedOnBranch(node[action], isOnDefaultBranch)
    );

    if (permissionAllowNode) {
      return { isAllowed: true };
    } else {
      const permissionDeniedNode = permission.find(
        ({ node }) => !isActionAllowedOnBranch(node[action], isOnDefaultBranch)
      );
      return {
        isAllowed: false,
        message: getMessage(action, permissionDeniedNode?.node?.[action]),
      };
    }
  };

  return {
    view: createPermissionAction("view"),
    create: createPermissionAction("create"),
    update: createPermissionAction("update"),
    delete: createPermissionAction("delete"),
  };
}

export const PERMISSION_ALLOW_ALL: Permission = {
  view: { isAllowed: true },
  create: { isAllowed: true },
  update: { isAllowed: true },
  delete: { isAllowed: true },
};
