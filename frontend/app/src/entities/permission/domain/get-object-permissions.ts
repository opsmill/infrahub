import type { ContextParams } from "@/shared/api/types";

import { getPermissionsFromApi } from "@/entities/permission/api/get-permissions-from-api";
import type { Permission } from "@/entities/permission/types";
import { type GetPermissionOptions, getPermission } from "@/entities/permission/utils";

export interface GetObjectPermissionsArgs extends ContextParams, GetPermissionOptions {
  kind: string;
}

export type GetObjectPermissions = (args: GetObjectPermissionsArgs) => Promise<Permission>;

export const getObjectPermissions: GetObjectPermissions = async ({
  branchName,
  atDate,
  branch,
  kind,
}) => {
  const { data } = await getPermissionsFromApi({ kind, branchName, atDate });

  const permissionData = data[kind]?.permissions?.edges ?? [];

  return getPermission(permissionData, { branch });
};
