import type { Permission } from "@/entities/permission/types";

export const PERMISSION_ALLOW_ALL: Permission = {
  create: { isAllowed: true },
  view: { isAllowed: true },
  update: { isAllowed: true },
  delete: { isAllowed: true },
};

export const PERMISSION_DENY_ALL: Permission = {
  create: { isAllowed: false, message: "Loading permissions..." },
  view: { isAllowed: false, message: "Loading permissions..." },
  update: { isAllowed: false, message: "Loading permissions..." },
  delete: { isAllowed: false, message: "Loading permissions..." },
};
