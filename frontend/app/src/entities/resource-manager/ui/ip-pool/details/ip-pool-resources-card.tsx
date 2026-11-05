import { Card, ListBox, ListBoxItem } from "@infrahub/ui";
import { Text } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { pluralize } from "@/shared/utils/string";

import type {
  IpPoolResource,
  IpPoolResourceUsage,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_PREFIX_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolUsageBar } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-usage-bar";
import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

interface NoResourcesCardProps {
  poolKind: IpPoolKind;
}

function NoResourcesCard({ poolKind }: NoResourcesCardProps) {
  const allocatedItems = poolKind === IP_PREFIX_POOL ? "prefixes" : "addresses";

  return (
    <Card className="min-w-64 items-start gap-1 px-4 py-3 text-sm">
      <p className="font-medium">No resource prefixes</p>
      <p className="text-pretty text-foreground-muted">
        This pool can't allocate {allocatedItems} until it has a resource prefix.
      </p>
      <p className="text-foreground-muted">Edit the pool to add one.</p>
    </Card>
  );
}

export interface IpPoolResourcesCardProps {
  poolId: string;
  poolKind: IpPoolKind;
  usage: IpPoolResourceUsage;
  resources: IpPoolResource[];
  selectedResourceId: string | null;
}

export function IpPoolResourcesCard({
  poolId,
  poolKind,
  usage,
  resources,
  selectedResourceId,
}: IpPoolResourcesCardProps) {
  if (resources.length === 0) return <NoResourcesCard poolKind={poolKind} />;

  return (
    <Card>
      <div className="px-3 pt-2 pb-1 font-medium text-foreground-muted text-sm">
        Resource prefixes
      </div>
      <section
        aria-label="All resource prefixes"
        className="mx-1 flex flex-col gap-1.5 px-2.5 py-2"
      >
        <Row className="justify-between gap-3">
          <span className="font-medium">All resource prefixes</span>
          <span className="shrink-0 text-foreground-muted text-xs">
            {pluralize(resources.length, "resource prefix", "es")}
          </span>
        </Row>
        <IpPoolUsageBar usage={usage} />
      </section>
      <ListBox
        aria-label="Resource prefixes"
        selectionMode="single"
        selectionIndicator="highlight"
        selectedKeys={
          selectedResourceId !== null && resources.some(({ id }) => id === selectedResourceId)
            ? [selectedResourceId]
            : []
        }
        items={resources}
      >
        {(resource) => (
          <ListBoxItem
            id={resource.id}
            href={getIpPoolResourceUrl(poolId, resource.id)}
            textValue={resource.display_label}
            className="flex-col items-stretch gap-1.5 rounded-xl px-2.5 py-2"
          >
            <Row className="justify-between gap-3">
              <Text slot="label" className="min-w-0 truncate font-medium tabular-nums">
                {resource.display_label}
              </Text>
              {resource.allocationWeight !== null && (
                <Text slot="description" className="shrink-0 text-foreground-muted text-xs">
                  Weight {resource.allocationWeight}
                </Text>
              )}
            </Row>
            <IpPoolUsageBar usage={resource.usage} />
          </ListBoxItem>
        )}
      </ListBox>
    </Card>
  );
}
