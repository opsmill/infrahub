import { Card, CardHeader, ListBox, ListBoxItem, Tooltip } from "@infrahub/ui";
import { Text } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { formatNumberDisplay } from "@/shared/utils/number";

import type {
  IpPoolResource,
  IpPoolResourceUsage,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_PREFIX_POOL, type IpPoolKind } from "@/entities/resource-manager/domain/model/pool";
import { IpPoolUsageBar } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-usage-bar";
import { formatUsagePercent } from "@/entities/resource-manager/ui/pool/format-usage-percent";
import { UtilizationTooltipMessage } from "@/entities/resource-manager/ui/pool/utilization-tooltip-message";
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

interface ResourceCountProps {
  count: number;
}

function ResourceCount({ count }: ResourceCountProps) {
  return (
    <span className="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-content-strong px-1.5 font-medium text-foreground-muted text-xxs tabular-nums">
      {formatNumberDisplay(count)}
      <span className="sr-only"> {count === 1 ? "resource prefix" : "resource prefixes"}</span>
    </span>
  );
}

interface TotalUsageProps {
  usage: IpPoolResourceUsage;
}

function TotalUsage({ usage }: TotalUsageProps) {
  return (
    <Tooltip
      nonInteractiveTrigger
      message={
        <Row>
          <UtilizationTooltipMessage
            title="Default branch"
            value={formatUsagePercent(usage.utilizationDefaultBranch)}
          />
          <UtilizationTooltipMessage
            title="This branch only"
            value={formatUsagePercent(usage.utilizationBranches)}
          />
        </Row>
      }
    >
      <Row className="shrink-0 gap-1 text-xs">
        <span className="text-foreground-muted">Total usage</span>
        <span className="font-medium text-foreground tabular-nums">
          {formatUsagePercent(usage.utilization)}
        </span>
      </Row>
    </Tooltip>
  );
}

export interface IpPoolResourcesCardProps {
  poolId: string;
  poolKind: IpPoolKind;
  usage: IpPoolResourceUsage;
  resources: IpPoolResource[];
  areWeightsUnavailable?: boolean;
  selectedResourceId: string | null;
}

export function IpPoolResourcesCard({
  poolId,
  poolKind,
  usage,
  resources,
  areWeightsUnavailable = false,
  selectedResourceId,
}: IpPoolResourcesCardProps) {
  if (resources.length === 0) return <NoResourcesCard poolKind={poolKind} />;

  return (
    <Card className="overflow-hidden">
      <CardHeader variant="ghost" className="flex items-baseline justify-between">
        <Row className="gap-1">
          <h2>Resource prefixes</h2>
          <ResourceCount count={resources.length} />
        </Row>
        <TotalUsage usage={usage} />
      </CardHeader>
      {areWeightsUnavailable && (
        <p role="status" className="mx-1 px-2.5 pb-1 text-foreground-muted text-xs">
          The weights could not be loaded, so the list is sorted by prefix, not in the order the
          pool fills them.
        </p>
      )}
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
            <Row className="justify-between">
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
