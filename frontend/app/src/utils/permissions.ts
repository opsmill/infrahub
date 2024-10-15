export type PermissionProps = {
  view: string;
  create: string;
  update: string;
  delete: string;
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
  permission: PermissionProps | Array<{ node: PermissionProps }>
): Permission {
  const isPermissionArray = Array.isArray(permission);

  const isViewAllowed = isPermissionArray
    ? permission.some(({ node }) => node.view === "ALLOW")
    : permission.view === "ALLOW";

  const isCreateAllowed = isPermissionArray
    ? permission.some(({ node }) => node.create === "ALLOW")
    : permission.create === "ALLOW";

  const isUpdateAllowed = isPermissionArray
    ? permission.some(({ node }) => node.update === "ALLOW")
    : permission.update === "ALLOW";

  const isDeleteAllowed = isPermissionArray
    ? permission.some(({ node }) => node.delete === "ALLOW")
    : permission.delete === "ALLOW";

  return {
    view: isViewAllowed
      ? {
          isAllowed: true,
        }
      : {
          isAllowed: false,
          message: "You can't access this view",
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
