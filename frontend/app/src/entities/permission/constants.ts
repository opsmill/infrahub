import type { Permission } from "@/entities/permission/types";

/** Global permission action that gates managing organisation-wide preferences. */
export const MANAGE_GLOBAL_PREFERENCES = "manage_global_preferences";

/** Global permission held by super admins; it bypasses every other global permission check. */
export const SUPER_ADMIN = "super_admin";

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
