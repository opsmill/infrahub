import {
  type GetGlobalPermissionsFromApiParams,
  getGlobalPermissionsFromApi,
} from "@/entities/role-manager/api/get-global-permissions-from-api";

export type GetGlobalPermissionsParams = GetGlobalPermissionsFromApiParams;

export async function getGlobalPermissions(params: GetGlobalPermissionsParams) {
  const { data, errors } = await getGlobalPermissionsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
