export const ACCOUNT_TABLE_ATTRIBUTES = ["name", "description", "account_type", "status"];
export const ACCOUNT_TABLE_RELATIONSHIPS = ["member_of_groups"];

export const GROUP_TABLE_ATTRIBUTES = ["name", "description", "label", "group_type"];
export const GROUP_TABLE_RELATIONSHIPS = ["members", "roles"];

export const ROLE_TABLE_ATTRIBUTES = ["name", "description"];
export const ROLE_TABLE_RELATIONSHIPS = ["groups", "permissions"];

export const GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES = ["action", "decision"];
export const GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS = ["roles"];

export const OBJECT_PERMISSION_TABLE_ATTRIBUTES = ["action", "decision"];
export const OBJECT_PERMISSION_TABLE_RELATIONSHIPS = ["roles"];
