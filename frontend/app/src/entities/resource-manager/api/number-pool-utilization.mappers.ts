import type {
  NumberPoolUtilizationFiguresNode,
  NumberPoolUtilizationNode,
} from "@/entities/resource-manager/api/get-number-pool-utilization-from-api";
import type {
  NumberPoolUsage,
  NumberPoolUtilization,
} from "@/entities/resource-manager/domain/model/number-pool";
import { NUMBER_POOL_RANGE_KIND } from "@/entities/resource-manager/domain/model/pool";

// BigInt fields reach the client untyped, as a JSON number or string.
export const toNumber = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const mapToNumberPoolUsage = (figures: NumberPoolUtilizationFiguresNode): NumberPoolUsage => ({
  size: toNumber(figures.size),
  used: toNumber(figures.used),
  usedDefaultBranch: toNumber(figures.used_default_branch),
  usedBranches: toNumber(figures.used_branches),
  utilization: figures.utilization,
});

export const mapToNumberPoolUtilization = (
  node: NumberPoolUtilizationNode
): NumberPoolUtilization => ({
  usage: mapToNumberPoolUsage(node.figures),
  ranges: node.ranges.map((range) => ({
    id: range.id,
    __typename: NUMBER_POOL_RANGE_KIND,
    start: { value: toNumber(range.start) },
    end: { value: toNumber(range.end) },
    allocation_weight: { value: toNumber(range.weight) },
    usage: mapToNumberPoolUsage(range.figures),
  })),
});
