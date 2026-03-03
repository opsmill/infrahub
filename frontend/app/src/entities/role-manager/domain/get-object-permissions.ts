import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import {
  type GetObjectPermissionsFromApiParams,
  getObjectPermissionsFromApi,
} from "@/entities/role-manager/api/get-object-permissions-from-api";

export type GetObjectPermissionsParams = GetObjectPermissionsFromApiParams;

export interface ObjectPermissionRoleItem {
  id: string;
  display_label: string | null | undefined;
}

export interface ObjectPermissionItem {
  id: string;
  display_label: string | null | undefined;
  hfid: string[] | null | undefined;
  name: string | null | undefined;
  namespace: string | null | undefined;
  action: string | null | undefined;
  decision: string | number | null | undefined;
  identifier: string | null | undefined;
  roles: ObjectPermissionRoleItem[];
}

export interface ObjectPermissionListResult {
  objectPermissions: ObjectPermissionItem[];
  count: number | undefined;
  permission: Permission;
}

export async function getObjectPermissions(
  params: GetObjectPermissionsParams
): Promise<ObjectPermissionListResult> {
  const { data, errors } = await getObjectPermissionsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const root = data?.CoreObjectPermission;

  const permission = getPermission(root?.permissions?.edges);

  const objectPermissions: ObjectPermissionItem[] =
    root?.edges.map((edge) => ({
      id: edge?.node?.id ?? "",
      display_label: edge?.node?.display_label,
      hfid: edge?.node?.hfid,
      name: edge?.node?.name?.value,
      namespace: edge?.node?.namespace?.value,
      action: edge?.node?.action?.value,
      decision: edge?.node?.decision?.value as string | number | null | undefined,
      identifier: edge?.node?.identifier?.value,
      roles:
        edge?.node?.roles?.edges?.map((roleEdge) => ({
          id: roleEdge?.node?.id ?? "",
          display_label: roleEdge?.node?.display_label,
        })) ?? [],
    })) ?? [];

  return {
    objectPermissions,
    count: root?.count ?? undefined,
    permission,
  };
}
