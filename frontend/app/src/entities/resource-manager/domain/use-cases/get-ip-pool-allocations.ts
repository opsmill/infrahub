import {
  type GetIpPoolAllocationsFromApiParams,
  getIpPoolAllocationsFromApi,
} from "@/entities/resource-manager/api/get-ip-pool-allocations-from-api";
import { mapToIpPoolAllocationsPage } from "@/entities/resource-manager/api/ip-pool-allocation.mappers";
import type { IpPoolAllocationsPage } from "@/entities/resource-manager/domain/model/ip-pool";

export type GetIpPoolAllocationsParams = GetIpPoolAllocationsFromApiParams;

export type GetIpPoolAllocationsResult = IpPoolAllocationsPage;

export const getIpPoolAllocations = async (
  params: GetIpPoolAllocationsParams
): Promise<GetIpPoolAllocationsResult> => {
  const { data, errors } = await getIpPoolAllocationsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return mapToIpPoolAllocationsPage(data.InfrahubResourcePoolAllocated);
};
