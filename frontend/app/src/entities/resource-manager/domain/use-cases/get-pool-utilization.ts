import {
  type GetPoolUtilizationFromApiParams,
  getPoolUtilizationFromApi,
} from "@/entities/resource-manager/api/get-pool-utilization-from-api";

export type GetPoolUtilizationParams = GetPoolUtilizationFromApiParams;

export const getPoolUtilization = async (params: GetPoolUtilizationParams) => {
  const { data, errors } = await getPoolUtilizationFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubResourcePoolUtilization;
};
