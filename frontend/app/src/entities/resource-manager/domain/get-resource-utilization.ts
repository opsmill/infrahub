import {
  type GetResourceUtilizationFromApiParams,
  getResourceUtilizationFromApi,
} from "@/entities/resource-manager/api/get-resource-utilization-from-api";
import { RESOURCE_POOL_UTILIZATION_KIND } from "@/entities/resource-manager/constants";

export type GetResourcePoolUtilizationParams = GetResourceUtilizationFromApiParams;

export const getResourceUtilization = async (params: GetResourcePoolUtilizationParams) => {
  const { data, errors } = await getResourceUtilizationFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data[RESOURCE_POOL_UTILIZATION_KIND];
};
