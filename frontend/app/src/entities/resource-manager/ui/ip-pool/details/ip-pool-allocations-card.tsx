import { Card } from "@infrahub/ui";
import { ArrowLeftIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";

import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolAllocationsTable } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-table";
import { PoolItemNotFound } from "@/entities/resource-manager/ui/pool/pool-item-not-found";
import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

interface NoResourceSelectedProps {
  poolKind: IpPoolKind;
}

function NoResourceSelected({ poolKind }: NoResourceSelectedProps) {
  const allocatedItems = poolKind === IP_ADDRESS_POOL ? "IP addresses" : "IP prefixes";

  return (
    <Col className="min-h-64 grow items-start self-stretch rounded-2xl border border-border-strong border-dashed px-4 py-3">
      <Col className="gap-1">
        <Row className="gap-1.5">
          <ArrowLeftIcon className="size-4 shrink-0 text-foreground-muted" aria-hidden />
          <h2 className="font-medium text-sm">Select a resource prefix</h2>
        </Row>
        <p className="text-pretty text-foreground-muted text-sm">
          See all {allocatedItems} allocated from it.
        </p>
      </Col>
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
  if (selectedResourceId === null) return <NoResourceSelected poolKind={poolKind} />;

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
