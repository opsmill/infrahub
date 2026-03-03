import {
  type GetGroupsFromApiParams,
  getGroupsFromApi,
} from "@/entities/groups/api/get-groups-from-api";
import type { Group } from "@/entities/groups/domain/types";
import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";

export type GetGroupsParams = GetGroupsFromApiParams;

export interface GetGroupsResult {
  groups: Array<Group>;
  permission: Permission;
}

export async function getGroups(params: GetGroupsParams): Promise<GetGroupsResult> {
  const { data, errors } = await getGroupsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const kindData = data?.[params.objectKind];
  const objectNode = kindData?.edges?.[0]?.node;
  const permission = getPermission(kindData?.permissions?.edges);

  const groups: Array<Group> =
    objectNode?.member_of_groups?.edges?.map(({ node }: { node: Group }) => node) ?? [];

  return { groups, permission };
}
