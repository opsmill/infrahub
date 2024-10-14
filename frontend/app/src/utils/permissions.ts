import { IModelSchema } from "@/state/atoms/schema.atom";

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
  return {
    view: {
      isAllowed: isPermissionArray
        ? permission.some(({ node }) => node.view === "ALLOW")
        : permission.view === "ALLOW",
      message: "You can't access this view.",
    },
    create: {
      isAllowed: isPermissionArray
        ? permission.some(({ node }) => node.create === "ALLOW")
        : permission.create === "ALLOW",
      message: "You can't create this object.",
    },
    update: {
      isAllowed: isPermissionArray
        ? permission.some(({ node }) => node.update === "ALLOW")
        : permission.update === "ALLOW",
      message: "You can't update this object.",
    },
    delete: {
      isAllowed: isPermissionArray
        ? permission.some(({ node }) => node.delete === "ALLOW")
        : permission.delete === "ALLOW",
      message: "You can't delete this object.",
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
