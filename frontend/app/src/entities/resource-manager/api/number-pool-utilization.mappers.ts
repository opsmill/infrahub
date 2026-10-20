import type {
  NumberPoolUtilizationFiguresNode,
  NumberPoolUtilizationNode,
} from "@/entities/resource-manager/api/get-number-pool-utilization-from-api";
import type {
  NumberPoolUsage,
  NumberPoolUtilization,
} from "@/entities/resource-manager/domain/model/number-pool";
import { NUMBER_POOL_RANGE_KIND } from "@/entities/resource-manager/domain/model/pool";

export const mapToNumberPoolUsage = (
  figures: NumberPoolUtilizationFiguresNode
): NumberPoolUsage => ({
  size: figures.size,
  used: figures.used,
  usedDefaultBranch: figures.used_default_branch,
  usedBranches: figures.used_branches,
  utilization: figures.utilization,
});

export const mapToNumberPoolUtilization = (
  node: NumberPoolUtilizationNode
): NumberPoolUtilization => ({
  usage: mapToNumberPoolUsage(node.figures),
  ranges: node.ranges.map((range) => ({
    id: range.id,
    __typename: NUMBER_POOL_RANGE_KIND,
    start: { value: range.start },
    end: { value: range.end },
    allocation_weight: { value: range.weight },
    usage: mapToNumberPoolUsage(range.figures),
  })),
});
