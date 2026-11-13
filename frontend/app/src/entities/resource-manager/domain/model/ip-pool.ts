import type { NodeAttribute, NodeCore } from "@/entities/nodes/object/domain/model/node";
import type {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
} from "@/entities/resource-manager/domain/model/pool";

export const IP_POOL_MEMBER_TYPE_PREFIX = "prefix";
export const IP_POOL_MEMBER_TYPE_ADDRESS = "address";
export type IpPoolMemberType =
  | typeof IP_POOL_MEMBER_TYPE_PREFIX
  | typeof IP_POOL_MEMBER_TYPE_ADDRESS;

export const WEIGHTED_POOL_RESOURCE_GENERIC = "CoreWeightedPoolResource";

export interface IpPoolNamespace {
  id: string;
  display_label: string;
  isDefault: boolean;
}

interface IpPoolBase extends NodeCore {
  name: NodeAttribute<string>;
  description: NodeAttribute<string | null>;
  default_prefix_length: NodeAttribute<number | null>;
  ip_namespace: IpPoolNamespace;
}

export interface IpPrefixPoolData extends IpPoolBase {
  __typename: typeof IP_PREFIX_POOL;
  default_prefix_type: NodeAttribute<string | null>;
  default_member_type: NodeAttribute<IpPoolMemberType | null>;
}

export interface IpAddressPoolData extends IpPoolBase {
  __typename: typeof IP_ADDRESS_POOL;
  default_address_type: NodeAttribute<string | null>;
}

export type IpPoolData = IpPrefixPoolData | IpAddressPoolData;

// percentages from 0 to 100; utilizationBranches is the share the viewing branch adds to the default branch
export interface IpPoolResourceUsage {
  utilization: number;
  utilizationDefaultBranch: number;
  utilizationBranches: number;
}

export interface IpPoolResource extends NodeCore {
  display_label: string;
  allocationWeight: number | null;
  usage: IpPoolResourceUsage;
}

export interface IpPoolUtilization {
  usage: IpPoolResourceUsage;
  resources: IpPoolResource[];
}

export interface IpPoolAllocation extends NodeCore {
  display_label: string;
  identifier: string | null;
}

export interface IpPoolAllocationsPage {
  count: number;
  allocations: IpPoolAllocation[];
}

export type IpPoolDefaultValue =
  | { type: "kind"; kind: string }
  | { type: "prefix-length"; length: number }
  | { type: "member-type"; memberType: IpPoolMemberType };

export interface IpPoolDefaultEntry {
  label: string;
  value: IpPoolDefaultValue | null;
  fallbackPhrase: string;
}
