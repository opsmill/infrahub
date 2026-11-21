import type { IpPoolUtilizationNode } from "@/entities/resource-manager/api/get-ip-pool-utilization-from-api";
import type {
  IpPoolResource,
  IpPoolResourceUsage,
  IpPoolUtilization,
} from "@/entities/resource-manager/domain/model/ip-pool";

interface UsageFigures {
  utilization: number;
  utilization_default_branch: number;
  utilization_branches: number;
}

export const mapToIpPoolResourceUsage = (figures: UsageFigures): IpPoolResourceUsage => ({
  utilization: figures.utilization,
  utilizationDefaultBranch: figures.utilization_default_branch,
  utilizationBranches: figures.utilization_branches,
});

export const mapToIpPoolUtilization = (
  node: IpPoolUtilizationNode,
  weightsById: ReadonlyMap<string, number | null>
): IpPoolUtilization => ({
  usage: mapToIpPoolResourceUsage(node),
  resources: node.edges.map(
    ({ node: resource }): IpPoolResource => ({
      id: resource.id,
      __typename: resource.kind,
      display_label: resource.display_label,
      allocationWeight: weightsById.get(resource.id) ?? null,
      usage: mapToIpPoolResourceUsage(resource),
    })
  ),
});
