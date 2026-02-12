import type { ContextParams } from "@/shared/api/types";

import { getPermissionsFromApi } from "@/entities/permission/api/get-permissions-from-api";
import type { Permission } from "@/entities/permission/types";
import { type GetPermissionOptions, getPermission } from "@/entities/permission/utils";

export type GetObjectPermissions = (
  args: ContextParams & GetPermissionOptions
) => Promise<Permission>;

export const getObjectPermissions: GetObjectPermissions = async ({
  branchName,
  atDate,
  branch,
  schema,
}) => {
  const kind = schema?.kind as string;
  const { data } = await getPermissionsFromApi({ kind, branchName, atDate });

  const permissionData = data[kind].permissions?.edges ?? [];

  return getPermission(permissionData, { branch, schema });
};
