import {
  Permission,
  PermissionAction,
  PermissionData,
  PermissionDecision,
  PermissionDecisionData,
} from "@/screens/permission/types";
import { store } from "@/state";
import { configState } from "@/state/atoms/config.atom";
import { warnUnexpectedType } from "@/utils/common";

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

export function getPermission(permission?: Array<{ node: PermissionData }>): Permission {
  if (!Array.isArray(permission)) return PERMISSION_ALLOW_ALL;

  const config = store.get(configState);

  const createPermissionAction = (action: PermissionAction): PermissionDecision => {
    if (action === "view" && config?.main.allow_anonymous_access) return { isAllowed: true };

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
