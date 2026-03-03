import type { NodeCore } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import {
  type GetRolesFromApiParams,
  getRolesFromApi,
} from "@/entities/role-manager/api/get-roles-from-api";

export type GetRolesParams = GetRolesFromApiParams;

export interface RolePermissionItem extends NodeCore {
  identifier: string | null | undefined;
}

export interface RoleItem extends NodeCore {
  name: string | null | undefined;
  groups: NodeCore[];
  permissions: RolePermissionItem[];
}

export interface RoleListResult {
  roles: RoleItem[];
  count: number | null | undefined;
  permission: Permission;
}

export async function getRoles(params: GetRolesParams): Promise<RoleListResult> {
  const { data, errors } = await getRolesFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const root = data?.CoreAccountRole;

  const permission = getPermission(root?.permissions?.edges);

  const roles: RoleItem[] =
    root?.edges.map((edge) => ({
      id: edge?.node?.id ?? "",
      display_label: edge?.node?.display_label,
      hfid: edge?.node?.hfid,
      __typename: edge?.node?.__typename ?? "",
      name: edge?.node?.name?.value,
      groups:
        edge?.node?.groups?.edges?.map((groupEdge) => ({
          id: groupEdge?.node?.id ?? "",
          display_label: groupEdge?.node?.display_label,
          hfid: groupEdge?.node?.hfid,
          __typename: groupEdge?.node?.__typename ?? "",
        })) ?? [],
      permissions:
        edge?.node?.permissions?.edges?.map((permEdge) => ({
          id: permEdge?.node?.id ?? "",
          display_label: permEdge?.node?.display_label,
          hfid: permEdge?.node?.hfid,
          __typename: permEdge?.node?.__typename ?? "",
          identifier: permEdge?.node?.identifier?.value,
        })) ?? [],
    })) ?? [];

  return {
    roles,
    count: root?.count,
    permission,
  };
}
