import type { Permission } from "@/entities/permission/types";

export const PERMISSION_ALLOW_ALL: Permission = {
  create: { isAllowed: true },
  view: { isAllowed: true },
  update: { isAllowed: true },
  delete: { isAllowed: true },
};
