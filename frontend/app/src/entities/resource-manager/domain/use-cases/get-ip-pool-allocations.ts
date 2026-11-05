import {
  type GetIpPoolAllocationsFromApiParams,
  getIpPoolAllocationsFromApi,
} from "@/entities/resource-manager/api/get-ip-pool-allocations-from-api";
import { mapToIpPoolAllocationsPage } from "@/entities/resource-manager/api/ip-pool-allocation.mappers";
import { throwGraphQLErrors } from "@/entities/resource-manager/api/throw-graphql-errors";
import type { IpPoolAllocationsPage } from "@/entities/resource-manager/domain/model/ip-pool";

export type GetIpPoolAllocationsParams = GetIpPoolAllocationsFromApiParams;

export type GetIpPoolAllocationsResult = IpPoolAllocationsPage;

export const getIpPoolAllocations = async (
  params: GetIpPoolAllocationsParams
): Promise<GetIpPoolAllocationsResult> => {
  const { data, errors } = await getIpPoolAllocationsFromApi(params);

  throwGraphQLErrors(errors);

  return mapToIpPoolAllocationsPage(data.InfrahubResourcePoolAllocated);
};
