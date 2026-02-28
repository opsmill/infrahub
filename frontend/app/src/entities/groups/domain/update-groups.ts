import {
  type UpdateGroupsFromApiParams,
  updateGroupsFromApi,
} from "@/entities/groups/api/update-groups-from-api";

export type UpdateGroupsParams = UpdateGroupsFromApiParams;

export async function updateGroups(params: UpdateGroupsParams) {
  const { data, errors } = await updateGroupsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
