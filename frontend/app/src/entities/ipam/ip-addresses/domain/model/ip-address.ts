import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export const IP_ADDRESS_GENERIC = "BuiltinIPAddress";
export const IP_ADDRESS_AVAILABLE_KIND = "InternalIPRangeAvailable" as const;

export interface IpAddressAvailableNode extends NodeCore {
  address: { value: string };
  last_address: { value: string };
  __typeName: typeof IP_ADDRESS_AVAILABLE_KIND;
}
