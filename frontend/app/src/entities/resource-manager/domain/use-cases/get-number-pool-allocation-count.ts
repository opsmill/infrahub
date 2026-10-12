import {
  type GetNumberPoolAllocationCountFromApiParams,
  getNumberPoolAllocationCountFromApi,
} from "@/entities/resource-manager/api/get-number-pool-allocation-count-from-api";
import { toNumber } from "@/entities/resource-manager/api/number-pool-utilization.mappers";

export type GetNumberPoolAllocationCountParams = GetNumberPoolAllocationCountFromApiParams;

export const getNumberPoolAllocationCount = async (
  params: GetNumberPoolAllocationCountParams
): Promise<number> => {
  const { data, errors } = await getNumberPoolAllocationCountFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return toNumber(data.InfrahubNumberPoolAllocations.count);
};
