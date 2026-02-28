import {
  type GetGroupsFromApiParams,
  getGroupsFromApi,
} from "@/entities/groups/api/get-groups-from-api";

export type GetGroupsParams = GetGroupsFromApiParams;

export async function getGroups(params: GetGroupsParams) {
  const { data, errors } = await getGroupsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
