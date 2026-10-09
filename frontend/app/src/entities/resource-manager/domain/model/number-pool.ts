import type { NodeAttribute, NodeCore } from "@/entities/nodes/object/domain/model/node";
import type {
  NUMBER_POOL_KIND,
  NUMBER_POOL_RANGE_KIND,
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

export interface NumberPoolUsage {
  size: number;
  used: number;
  usedDefaultBranch: number;
  usedBranches: number;
  utilization: number;
}

export interface NumberPoolRange extends NodeCore {
  __typename: typeof NUMBER_POOL_RANGE_KIND;
  start: NodeAttribute<number>;
  end: NodeAttribute<number>;
  allocation_weight: NodeAttribute<number>;
  usage: NumberPoolUsage;
}

export interface NumberPoolUtilization {
  usage: NumberPoolUsage;
  ranges: NumberPoolRange[];
}

export const NUMBER_POOL_PROVENANCE_ALLOCATED = "ALLOCATED";
export const NUMBER_POOL_PROVENANCE_PROVIDED = "PROVIDED";

export type NumberPoolProvenance =
  | typeof NUMBER_POOL_PROVENANCE_ALLOCATED
  | typeof NUMBER_POOL_PROVENANCE_PROVIDED;

export interface NumberPoolAllocation {
  value: number;
  branch: string;
  holder: NodeCore;
  provenance: NumberPoolProvenance;
  rangeId: string;
}
