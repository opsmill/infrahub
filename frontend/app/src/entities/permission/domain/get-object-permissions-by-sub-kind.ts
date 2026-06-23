import type { ContextParams } from "@/shared/api/types";

import { getPermissionsFromApi } from "@/entities/permission/api/get-permissions-from-api";
import type { Permission, PermissionData } from "@/entities/permission/types";
import { type GetPermissionOptions, getPermission } from "@/entities/permission/utils";

export interface GetObjectPermissionsBySubKindArgs extends ContextParams, GetPermissionOptions {
  kind: string;
}

export type ObjectPermissionsBySubKind = Record<string, Permission>;

export async function getObjectPermissionsBySubKind({
  branchName,
  atDate,
  branch,
  kind,
}: GetObjectPermissionsBySubKindArgs): Promise<ObjectPermissionsBySubKind> {
  const { data } = await getPermissionsFromApi({ kind, branchName, atDate });

  const edges: Array<{ node: PermissionData }> = data[kind]?.permissions?.edges ?? [];

  const grouped: Record<string, Array<{ node: PermissionData }>> = {};
  for (const edge of edges) {
    (grouped[edge.node.kind] ??= []).push(edge);
  }

  const result: ObjectPermissionsBySubKind = {};
  for (const [subKind, subKindEdges] of Object.entries(grouped)) {
    result[subKind] = getPermission(subKindEdges, { branch });
  }
  return result;
}
