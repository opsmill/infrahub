import {
  type GetNumberPoolUtilizationFromApiParams,
  getNumberPoolUtilizationFromApi,
} from "@/entities/resource-manager/api/get-number-pool-utilization-from-api";
import { mapToNumberPoolUtilization } from "@/entities/resource-manager/api/number-pool-utilization.mappers";
import type { NumberPoolUtilization } from "@/entities/resource-manager/domain/model/number-pool";
import { sortRangesByFillOrder } from "@/entities/resource-manager/domain/rules/sort-ranges-by-fill-order";

export type GetNumberPoolUtilizationParams = GetNumberPoolUtilizationFromApiParams;

export const getNumberPoolUtilization = async (
  params: GetNumberPoolUtilizationParams
): Promise<NumberPoolUtilization> => {
  const { data, errors } = await getNumberPoolUtilizationFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const utilization = mapToNumberPoolUtilization(data.InfrahubNumberPoolUtilization);

  return { ...utilization, ranges: sortRangesByFillOrder(utilization.ranges) };
};
