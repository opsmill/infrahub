import {
  type GetIpAddressPoolFromApiParams,
  getIpAddressPoolFromApi,
} from "@/entities/resource-manager/api/get-ip-address-pool-from-api";
import {
  type GetIpPrefixPoolFromApiParams,
  getIpPrefixPoolFromApi,
} from "@/entities/resource-manager/api/get-ip-prefix-pool-from-api";
import {
  mapToIpAddressPoolData,
  mapToIpPrefixPoolData,
} from "@/entities/resource-manager/api/ip-pool.mappers";
import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";

export interface GetIpPoolParams
  extends GetIpPrefixPoolFromApiParams,
    GetIpAddressPoolFromApiParams {
  poolKind: IpPoolKind;
}

export type GetIpPoolResult = IpPoolData;

const IP_POOL_NOT_FOUND = "IP pool not found";

const getIpAddressPool = async (params: GetIpAddressPoolFromApiParams) => {
  const { data } = await getIpAddressPoolFromApi(params);
  const node = data?.CoreIPAddressPool.edges[0]?.node;
  if (!node) throw new Error(IP_POOL_NOT_FOUND);

  return mapToIpAddressPoolData(node);
};

const getIpPrefixPool = async (params: GetIpPrefixPoolFromApiParams) => {
  const { data } = await getIpPrefixPoolFromApi(params);
  const node = data?.CoreIPPrefixPool.edges[0]?.node;
  if (!node) throw new Error(IP_POOL_NOT_FOUND);

  return mapToIpPrefixPoolData(node);
};

export const getIpPool = ({ poolKind, ...params }: GetIpPoolParams): Promise<GetIpPoolResult> =>
  poolKind === IP_ADDRESS_POOL ? getIpAddressPool(params) : getIpPrefixPool(params);
