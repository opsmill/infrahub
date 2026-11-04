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

export const getIpPool = async (params: GetIpPoolParams): Promise<IpPoolData> => {
  const { data, errors } = await getIpPoolFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const prefixPool = data?.CoreIPPrefixPool.edges[0]?.node;
  if (prefixPool) return mapToIpPrefixPoolData(prefixPool);

  const addressPool = data?.CoreIPAddressPool.edges[0]?.node;
  if (addressPool) return mapToIpAddressPoolData(addressPool);

  throw new Error("IP pool not found");
};
