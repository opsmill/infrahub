import type {
  NodeAttribute,
  NodeCore,
  NodeRelationship,
} from "@/entities/nodes/object/domain/model/node";

export type IpPrefixNode = NodeCore & {
  parent?: { node: NodeCore & { ancestors: { count: number } } };
  ancestors: { count: number };
  children: { count: number };
  ip_addresses: { count: number };
} & { [key: string]: NodeAttribute | NodeRelationship };
