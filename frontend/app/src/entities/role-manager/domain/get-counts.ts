import {
  type GetCountsFromApiParams,
  getCountsFromApi,
} from "@/entities/role-manager/api/get-counts-from-api";

export type GetCountsParams = GetCountsFromApiParams;

export interface RoleManagerCounts {
  accounts: number | null | undefined;
  groups: number | null | undefined;
  roles: number | null | undefined;
  globalPermissions: number | null | undefined;
  objectPermissions: number | null | undefined;
}

export async function getCounts(params: GetCountsParams): Promise<RoleManagerCounts> {
  const { data, errors } = await getCountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return {
    accounts: data?.CoreGenericAccount?.count,
    groups: data?.CoreAccountGroup?.count,
    roles: data?.CoreAccountRole?.count,
    globalPermissions: data?.CoreGlobalPermission?.count,
    objectPermissions: data?.CoreObjectPermission?.count,
  };
}
