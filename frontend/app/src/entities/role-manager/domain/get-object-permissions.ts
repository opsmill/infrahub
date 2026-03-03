import {
  type GetObjectPermissionsFromApiParams,
  getObjectPermissionsFromApi,
} from "@/entities/role-manager/api/get-object-permissions-from-api";

export type GetObjectPermissionsParams = GetObjectPermissionsFromApiParams;

export async function getObjectPermissions(params: GetObjectPermissionsParams) {
  const { data, errors } = await getObjectPermissionsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
