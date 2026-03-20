import {
  type GetCountsFromApiParams,
  getCountsFromApi,
} from "@/entities/role-manager/api/get-counts-from-api";

export type GetCountsParams = GetCountsFromApiParams;

export async function getCounts(params: GetCountsParams) {
  const { data, errors } = await getCountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
