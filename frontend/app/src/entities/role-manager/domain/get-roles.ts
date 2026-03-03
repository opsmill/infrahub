import {
  type GetRolesFromApiParams,
  getRolesFromApi,
} from "@/entities/role-manager/api/get-roles-from-api";

export type GetRolesParams = GetRolesFromApiParams;

export async function getRoles(params: GetRolesParams) {
  const { data, errors } = await getRolesFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
