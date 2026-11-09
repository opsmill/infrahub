import type {
  NodeAttribute,
  NodeCore,
  NodeRelationship,
} from "@/entities/nodes/object/domain/model/node";

export const IP_PREFIX_GENERIC = "BuiltinIPPrefix";
export const IP_PREFIX_AVAILABLE_KIND = "InternalIPPrefixAvailable";

export const IP_PREFIX_RELATIONSHIP_NAME = "ip_prefix";

// Shown in dedicated IPAM tabs/tables, so hidden from the details summary card
export const IP_PREFIX_SUMMARY_EXCLUDED_RELATIONSHIPS = ["children", "ip_addresses"];

export type IpPrefixNode = NodeCore & {
  parent?: { node: NodeCore & { ancestors: { count: number } } };
  ancestors: { count: number };
  children: { count: number };
  ip_addresses: { count: number };
} & { [key: string]: NodeAttribute | NodeRelationship };
