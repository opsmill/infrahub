import { ContextParams } from "@/shared/api/types";

import { getPermissionsFromApi } from "@/entities/permission/api/get-permissions-from-api";
import { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";

export type GetObjectPermissions = (args: ContextParams & { kind: string }) => Promise<Permission>;

export const getObjectPermissions: GetObjectPermissions = async ({ kind, branchName, atDate }) => {
  const { data } = await getPermissionsFromApi({ kind, branchName, atDate });

  const permissionData = data[kind].permissions?.edges ?? [];

  return getPermission(permissionData);
};
