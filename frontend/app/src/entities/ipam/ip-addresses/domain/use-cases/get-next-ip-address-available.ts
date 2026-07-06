import {
  type GetNextIPAddressAvailableFromApiParams,
  getNextIpAddressAvailableFromApi,
} from "@/entities/ipam/ip-addresses/api/get-next-ip-address-available-from-api";

export type GetNextIpAddressAvailableParams = GetNextIPAddressAvailableFromApiParams;

export type GetNextIpAddressAvailable = (
  params: GetNextIpAddressAvailableParams
) => Promise<string>;

export const getNextIpAddressAvailable: GetNextIpAddressAvailable = async (params) => {
  const { data, errors } = await getNextIpAddressAvailableFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.InfrahubIPAddressGetNextAvailable.address;
};
