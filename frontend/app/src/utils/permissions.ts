import { Branch } from "@/generated/graphql";

type Action = "view" | "create" | "update" | "delete";

type Decision = "DENY" | "ALLOW_ALL" | "ALLOW_DEFAULT" | "ALLOW_OTHER";

const getAllowedValue = (decision: Decision, isOnDefaultBranch: boolean) => {
  if (decision === "ALLOW_ALL") return true;
  if (decision === "ALLOW_DEFAULT" && isOnDefaultBranch) return true;
  if (decision === "ALLOW_OTHER" && !isOnDefaultBranch) return true;
  return false;
};

const getMessage = (decision: Decision, action: string) => {
  switch (decision) {
    case "DENY": {
      return `You can't ${action} this object.`;
    }
    case "ALLOW_DEFAULT": {
      return `You can't ${action} this object in this branch. Switch to the default branch.`;
    }
    case "ALLOW_OTHER": {
      return `You can't ${action} this object in the default branch. Switch to another one.`;
    }
  }
};

export type PermissionAction =
  | {
      isAllowed: true;
    }
  | {
      isAllowed: false;
      message: string;
    };

export type Permission = {
  view: PermissionAction;
  create: PermissionAction;
  update: PermissionAction;
  delete: PermissionAction;
};

export function getPermission(
  permission: Array<{ node: Record<Action, Decision> }>,
  currentBranch: Branch | null
): Permission {
  const isOnDefaultBranch = !!currentBranch?.is_default;

  const isViewAllowed = permission.find(({ node }) =>
    getAllowedValue(node.view, isOnDefaultBranch)
  );

  const isCreateAllowed = permission.find(({ node }) =>
    getAllowedValue(node.create, isOnDefaultBranch)
  );

  const isUpdateAllowed = permission.find(({ node }) =>
    getAllowedValue(node.update, isOnDefaultBranch)
  );

  const isDeleteAllowed = permission.find(({ node }) =>
    getAllowedValue(node.delete, isOnDefaultBranch)
  );

  return {
    view: isViewAllowed
      ? {
          isAllowed: true,
        }
      : {
          isAllowed: false,
          message: "You can't access this object.",
        },
    create: isCreateAllowed
      ? {
          isAllowed: true,
        }
      : {
          isAllowed: false,
          message: "You can't create this object",
        },
    update: isUpdateAllowed
      ? {
          isAllowed: true,
        }
      : {
          isAllowed: false,
          message: "You can't update this object",
        },
    delete: isDeleteAllowed
      ? {
          isAllowed: true,
        }
      : {
          isAllowed: false,
          message: "You can't delete this object",
        },
  };
}

export const PERMISSION_ALLOW: Permission = {
  view: {
    isAllowed: true,
  },
  create: {
    isAllowed: true,
  },
  update: {
    isAllowed: true,
  },
  delete: {
    isAllowed: true,
  },
};
