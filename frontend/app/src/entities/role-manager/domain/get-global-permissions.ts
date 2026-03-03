import type { NodeCore } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import {
  type GetGlobalPermissionsFromApiParams,
  getGlobalPermissionsFromApi,
} from "@/entities/role-manager/api/get-global-permissions-from-api";

export type GetGlobalPermissionsParams = GetGlobalPermissionsFromApiParams;

export interface GlobalPermissionItem {
  id: string;
  display_label: string | null | undefined;
  hfid: (string | null)[] | null | undefined;
  __typename: string;
  action: string | null | undefined;
  decision: string | number | null | undefined;
  identifier: string | null | undefined;
  roles: NodeCore[];
}

export interface GlobalPermissionListResult {
  globalPermissions: GlobalPermissionItem[];
  count: number | null | undefined;
  permission: Permission;
}

export async function getGlobalPermissions(
  params: GetGlobalPermissionsParams
): Promise<GlobalPermissionListResult> {
  const { data, errors } = await getGlobalPermissionsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const root = data?.CoreGlobalPermission;

  const permission = getPermission(root?.permissions?.edges);

  const globalPermissions: GlobalPermissionItem[] =
    root?.edges.map((edge) => ({
      id: edge?.node?.id ?? "",
      display_label: edge?.node?.display_label,
      hfid: edge?.node?.hfid,
      __typename: edge?.node?.__typename ?? "",
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
    globalPermissions,
    count: root?.count,
    permission,
  };
}
