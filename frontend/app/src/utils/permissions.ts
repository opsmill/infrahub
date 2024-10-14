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

export function getPermission(permission: PermissionProps): Permission {
  return {
    view: {
      isAllowed: permission?.view === "ALLOW",
      message: "You can't access this view.",
    },
    create: {
      isAllowed: permission?.create === "ALLOW",
      message: "You can't create this object.",
    },
    update: {
      isAllowed: permission?.update === "ALLOW",
      message: "You can't update this object.",
    },
    delete: {
      isAllowed: permission?.delete === "ALLOW",
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
