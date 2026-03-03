import type { NodeCore } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import {
  type GetObjectPermissionsFromApiParams,
  getObjectPermissionsFromApi,
} from "@/entities/role-manager/api/get-object-permissions-from-api";

export type GetObjectPermissionsParams = GetObjectPermissionsFromApiParams;

export interface ObjectPermissionItem {
  id: string;
  display_label: string | null | undefined;
  hfid: (string | null)[] | null | undefined;
  __typename: string;
  name: string | null | undefined;
  namespace: string | null | undefined;
  action: string | null | undefined;
  decision: string | number | null | undefined;
  identifier: string | null | undefined;
  roles: NodeCore[];
}

export interface ObjectPermissionListResult {
  objectPermissions: ObjectPermissionItem[];
  count: number | null | undefined;
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
      __typename: edge?.node?.__typename ?? "",
      name: edge?.node?.name?.value,
      namespace: edge?.node?.namespace?.value,
      action: edge?.node?.action?.value,
      decision: edge?.node?.decision?.value,
      identifier: edge?.node?.identifier?.value,
      roles:
        edge?.node?.roles?.edges?.map((roleEdge) => ({
          id: roleEdge?.node?.id ?? "",
          display_label: roleEdge?.node?.display_label,
          hfid: roleEdge?.node?.hfid,
          __typename: roleEdge?.node?.__typename ?? "",
        })) ?? [],
    })) ?? [];

  return {
    objectPermissions,
    count: root?.count,
    permission,
  };
}
