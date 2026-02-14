import type { Permission } from "@/entities/permission/types";

export type GeneratePermissionOptions = {
  view?: boolean;
  create?: boolean;
  update?: boolean;
  delete?: boolean;
};

export const generatePermission = (options: GeneratePermissionOptions = {}): Permission => {
  const { view = true, create = true, update = true, delete: canDelete = true } = options;

  return {
    view: view ? { isAllowed: true } : { isAllowed: false, message: "View not allowed" },
    create: create ? { isAllowed: true } : { isAllowed: false, message: "Create not allowed" },
    update: update ? { isAllowed: true } : { isAllowed: false, message: "Update not allowed" },
    delete: canDelete ? { isAllowed: true } : { isAllowed: false, message: "Delete not allowed" },
  };
};
