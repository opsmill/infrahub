import { Card, ListBox, ListBoxItem } from "@infrahub/ui";
import { Text } from "react-aria-components";

import { Row } from "@/shared/components/container";

import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";
import { IpPoolUsageBar } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-usage-bar";
import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

const getSelectedKeys = (resources: IpPoolResource[], selectedResourceId: string | null) =>
  resources.some(({ id }) => id === selectedResourceId) && selectedResourceId !== null
    ? [selectedResourceId]
    : [];

function NoResourcesCard() {
  return (
    <Card className="min-w-64 items-start gap-1 px-4 py-3 text-sm">
      <p className="font-medium">No resource prefixes</p>
      <p className="text-pretty text-foreground-muted">
        This pool can't allocate until it has a resource prefix.
      </p>
      <p className="text-foreground-muted">Edit the pool to add one.</p>
    </Card>
  );
}

export interface IpPoolResourcesCardProps {
  poolId: string;
  resources: IpPoolResource[];
  selectedResourceId: string | null;
}

export function IpPoolResourcesCard({
  poolId,
  resources,
  selectedResourceId,
}: IpPoolResourcesCardProps) {
  if (resources.length === 0) return <NoResourcesCard />;

  return (
    <Card>
      <div className="px-3 pt-2 pb-1 font-medium text-foreground-muted text-sm">
        Resource prefixes
      </div>
      <ListBox
        aria-label="Resource prefixes"
        selectionMode="single"
        selectionIndicator="highlight"
        selectedKeys={getSelectedKeys(resources, selectedResourceId)}
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
              <Text slot="label" className="font-medium tabular-nums">
                {resource.display_label}
              </Text>
              {resource.allocationWeight !== null && (
                <Text slot="description" className="text-foreground-muted text-xs">
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
