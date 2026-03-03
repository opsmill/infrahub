import {
  type GetCountsFromApiParams,
  getCountsFromApi,
} from "@/entities/role-manager/api/get-counts-from-api";

export type GetCountsParams = GetCountsFromApiParams;

export interface RoleManagerCounts {
  accounts: number | undefined;
  groups: number | undefined;
  roles: number | undefined;
  globalPermissions: number | undefined;
  objectPermissions: number | undefined;
}

export async function getCounts(params: GetCountsParams): Promise<RoleManagerCounts> {
  const { data, errors } = await getCountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return {
    accounts: data?.CoreGenericAccount?.count ?? undefined,
    groups: data?.CoreAccountGroup?.count ?? undefined,
    roles: data?.CoreAccountRole?.count ?? undefined,
    globalPermissions: data?.CoreGlobalPermission?.count ?? undefined,
    objectPermissions: data?.CoreObjectPermission?.count ?? undefined,
  };
}
