import {
  type GetIpPoolFromApiParams,
  getIpPoolFromApi,
} from "@/entities/resource-manager/api/get-ip-pool-from-api";
import {
  mapToIpAddressPoolData,
  mapToIpPrefixPoolData,
} from "@/entities/resource-manager/api/ip-pool.mappers";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";

export type GetIpPoolParams = GetIpPoolFromApiParams;

export type GetIpPoolResult = IpPoolData;

export const getIpPool = async (params: GetIpPoolParams): Promise<GetIpPoolResult> => {
  const { data } = await getIpPoolFromApi(params);

  const prefixPool = data?.CoreIPPrefixPool.edges[0]?.node;
  if (prefixPool) return mapToIpPrefixPoolData(prefixPool);

  const addressPool = data?.CoreIPAddressPool.edges[0]?.node;
  if (addressPool) return mapToIpAddressPoolData(addressPool);

  throw new Error("IP pool not found");
};
