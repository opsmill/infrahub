import { Card, LinkButton } from "@infrahub/ui";
import { SearchXIcon } from "lucide-react";

import { Col } from "@/shared/components/container";

import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import type { IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolAllocationsTable } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-table";
import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

interface UnknownResourceProps {
  poolId: string;
}

function UnknownResource({ poolId }: UnknownResourceProps) {
  return (
    <Col className="items-center gap-4 px-6 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-content-muted text-foreground-muted">
        <SearchXIcon className="size-5" aria-hidden />
      </span>
      <Col className="max-w-sm items-center gap-1.5">
        <p className="font-medium">Resource prefix not found</p>
        <p className="text-pretty text-foreground-muted text-sm">
          The link points to a resource prefix this pool does not have. It may have been removed
          from the pool, or it may belong to another pool.
        </p>
      </Col>
      <LinkButton variant="outline" size="sm" href={getIpPoolResourceUrl(poolId)}>
        View the pool
      </LinkButton>
    </Col>
  );
}

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
        <UnknownResource poolId={poolId} />
      )}
    </Card>
  );
}
