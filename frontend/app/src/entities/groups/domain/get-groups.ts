import {
  type GetGroupsFromApiParams,
  getGroupsFromApi,
} from "@/entities/groups/api/get-groups-from-api";
import type { GroupDataFromAPI } from "@/entities/groups/api/types";
import { getPermission } from "@/entities/permission/utils";
import type { Permission } from "@/entities/permission/types";

export type GetGroupsParams = GetGroupsFromApiParams;

export interface GetGroupsResult {
  objectFound: boolean;
  groups: Array<GroupDataFromAPI>;
  permission: Permission;
}

export async function getGroups(params: GetGroupsParams): Promise<GetGroupsResult> {
  const { data, errors } = await getGroupsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const kindData = data?.[params.objectKind];
  const objectNode = kindData?.edges?.[0]?.node;
  const permission = getPermission(kindData?.permissions?.edges);

  if (!objectNode) {
    return { objectFound: false, groups: [], permission };
  }

  const groups: Array<GroupDataFromAPI> =
    objectNode.member_of_groups?.edges?.map(
      ({ node }: { node: GroupDataFromAPI }) => node
    ) ?? [];

  return { objectFound: true, groups, permission };
}
