import type { NodeAttribute, NodeCore } from "@/entities/nodes/object/domain/model/node";
import type {
  NUMBER_POOL_KIND,
  NumberPoolType,
} from "@/entities/resource-manager/domain/model/pool";

export interface NumberPool extends NodeCore {
  schemaKind: string;
  attributeName: string;
}

export interface NumberPoolData extends NodeCore {
  __typename: typeof NUMBER_POOL_KIND;
  name: NodeAttribute<string>;
  description: NodeAttribute<string | null>;
  pool_type: NodeAttribute<NumberPoolType>;
  node: NodeAttribute<string>;
  node_attribute: NodeAttribute<string>;
  allocation_scope: NodeAttribute<string[]>;
}
