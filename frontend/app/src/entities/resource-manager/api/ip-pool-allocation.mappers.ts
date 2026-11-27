import type { IpPoolAllocationsNode } from "@/entities/resource-manager/api/get-ip-pool-allocations-from-api";
import type { IpPoolAllocationsPage } from "@/entities/resource-manager/domain/model/ip-pool";

export const mapToIpPoolAllocationsPage = (node: IpPoolAllocationsNode): IpPoolAllocationsPage => ({
  count: Number(node.count),
  allocations: node.edges.map(({ node: allocation }) => ({
    id: allocation.id,
    __typename: allocation.kind,
    display_label: allocation.display_label,
    identifier: allocation.identifier ?? null,
  })),
});
