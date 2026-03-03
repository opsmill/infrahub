import {
  type UpdateGroupsFromApiParams,
  updateGroupsFromApi,
} from "@/entities/groups/api/update-groups-from-api";

export type UpdateGroupsParams = UpdateGroupsFromApiParams;

export async function updateGroups(params: UpdateGroupsParams) {
  const { data, errors } = await updateGroupsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data;
}
