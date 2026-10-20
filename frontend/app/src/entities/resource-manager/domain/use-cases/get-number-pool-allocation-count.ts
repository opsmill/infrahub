import {
  type GetNumberPoolAllocationCountFromApiParams,
  getNumberPoolAllocationCountFromApi,
} from "@/entities/resource-manager/api/get-number-pool-allocation-count-from-api";

export type GetNumberPoolAllocationCountParams = GetNumberPoolAllocationCountFromApiParams;

export const getNumberPoolAllocationCount = async (
  params: GetNumberPoolAllocationCountParams
): Promise<number> => {
  const { data, errors } = await getNumberPoolAllocationCountFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubNumberPoolAllocations.count;
};
