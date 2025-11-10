import type { IP_ADDRESS_AVAILABLE_KIND } from "@/entities/ipam/constants";
import type { NodeCore } from "@/entities/nodes/types";

export interface IpAddressAvailableNode extends NodeCore {
  address: { value: string };
  last_address: { value: string };
  __typeName: typeof IP_ADDRESS_AVAILABLE_KIND;
}
