import { Card } from "@infrahub/ui";

import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import type { IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolAllocationsTable } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-table";
import { PoolItemNotFound } from "@/entities/resource-manager/ui/pool/pool-item-not-found";
import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

export interface IpPoolAllocationsCardProps {
  poolId: string;
  poolKind: IpPoolKind;
  resources: IpPoolResource[];
  selectedResourceId: string | null;
}

export function IpPoolAllocationsCard({
  poolId,
  poolKind,
  resources,
  selectedResourceId,
}: IpPoolAllocationsCardProps) {
  if (resources.length === 0) return null;

  const resource = resources.find(({ id }) => id === selectedResourceId);

  return (
    <Card className="max-h-full grow overflow-hidden">
      {resource ? (
        <IpPoolAllocationsTable
          key={resource.id}
          poolId={poolId}
          poolKind={poolKind}
          resource={resource}
        />
      ) : (
        <PoolItemNotFound
          title="Resource prefix not found"
          description="The link points to a resource prefix this pool does not have. It may have been removed from the pool, or it may belong to another pool."
          href={getIpPoolResourceUrl(poolId)}
          linkLabel="View the pool"
        />
      )}
    </Card>
  );
}
