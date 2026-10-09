import type { NumberPoolAllocationNode } from "@/entities/resource-manager/api/get-number-pool-allocations-from-api";
import { toNumber } from "@/entities/resource-manager/api/number-pool-utilization.mappers";
import {
  NUMBER_POOL_PROVENANCE_ALLOCATED,
  NUMBER_POOL_PROVENANCE_PROVIDED,
  type NumberPoolAllocation,
  type NumberPoolProvenance,
} from "@/entities/resource-manager/domain/model/number-pool";

const toProvenance = (value: unknown): NumberPoolProvenance =>
  value === NUMBER_POOL_PROVENANCE_PROVIDED
    ? NUMBER_POOL_PROVENANCE_PROVIDED
    : NUMBER_POOL_PROVENANCE_ALLOCATED;

export const mapToNumberPoolAllocation = (
  node: NumberPoolAllocationNode
): NumberPoolAllocation => ({
  value: toNumber(node.value),
  branch: node.branch,
  holder: {
    id: node.holder.id,
    __typename: node.holder.kind,
    display_label: node.holder.display_label,
  },
  provenance: toProvenance(node.provenance),
  rangeId: node.range.id,
});
