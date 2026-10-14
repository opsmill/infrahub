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
  ranges: Array<{ start: number; end: number; allocation_weight: number | null }>;
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

// a peer id for a relationship; for an attribute, the value with the type the attribute stores
export type NumberPoolDivisionValue = string | number | boolean;

export interface NumberPoolDivisionEntry {
  path: string;
  value: NumberPoolDivisionValue;
  label: string;
  peerKind: string | null;
}

export interface NumberPoolDivision {
  label: string;
  entries: NumberPoolDivisionEntry[];
  usage: NumberPoolUsage;
}

export interface NumberPoolDivisions {
  fields: string[];
  divisions: NumberPoolDivision[];
}

export type NumberPoolDivisionSelector = Array<{ path: string; value: NumberPoolDivisionValue }>;

export const NUMBER_POOL_PROVENANCE_ALLOCATED = "ALLOCATED";
export const NUMBER_POOL_PROVENANCE_PROVIDED = "PROVIDED";

export type NumberPoolProvenance =
  | typeof NUMBER_POOL_PROVENANCE_ALLOCATED
  | typeof NUMBER_POOL_PROVENANCE_PROVIDED;

export const NUMBER_POOL_PROVENANCES = [
  NUMBER_POOL_PROVENANCE_ALLOCATED,
  NUMBER_POOL_PROVENANCE_PROVIDED,
] as const;

export interface NumberPoolAllocationFilters {
  branch?: string;
  provenance?: NumberPoolProvenance;
}

export interface NumberPoolAllocation {
  value: number;
  branch: string;
  holder: NodeCore;
  provenance: NumberPoolProvenance;
  rangeId: string;
}
