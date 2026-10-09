import {
  type GetNumberPoolAllocationsFromApiParams,
  getNumberPoolAllocationsFromApi,
} from "@/entities/resource-manager/api/get-number-pool-allocations-from-api";
import { mapToNumberPoolAllocation } from "@/entities/resource-manager/api/number-pool-allocation.mappers";
import type { NumberPoolAllocation } from "@/entities/resource-manager/domain/model/number-pool";

export type GetNumberPoolAllocationsParams = GetNumberPoolAllocationsFromApiParams;

export const getNumberPoolAllocations = async (
  params: GetNumberPoolAllocationsParams
): Promise<NumberPoolAllocation[]> => {
  const { data, errors } = await getNumberPoolAllocationsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubNumberPoolAllocations.allocations.map(mapToNumberPoolAllocation);
};
