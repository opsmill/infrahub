import {
  type GetGroupsFromApiParams,
  getRoleManagerGroupsFromApi,
} from "@/entities/role-manager/api/get-groups-from-api";

export type GetRoleManagerGroupsParams = GetGroupsFromApiParams;

export async function getRoleManagerGroups(params: GetRoleManagerGroupsParams) {
  const { data, errors } = await getRoleManagerGroupsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
