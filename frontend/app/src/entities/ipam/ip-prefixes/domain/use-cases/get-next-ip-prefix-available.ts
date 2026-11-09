import {
  type GetNextIPPrefixGetNextAvailableFromApiParams,
  getNextIpPrefixAvailableFromApi,
} from "@/entities/ipam/ip-prefixes/api/get-next-ip-prefix-available-from-api";

export type GetNextIpPrefixAvailableParams = GetNextIPPrefixGetNextAvailableFromApiParams;

export type GetNextIpPrefixAvailable = (params: GetNextIpPrefixAvailableParams) => Promise<string>;

export const getNextIpPrefixAvailable: GetNextIpPrefixAvailable = async (params) => {
  const { data, errors } = await getNextIpPrefixAvailableFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubIPPrefixGetNextAvailable.prefix;
};
