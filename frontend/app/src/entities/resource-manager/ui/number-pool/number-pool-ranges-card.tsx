import { Card, ListBox, ListBoxItem } from "@infrahub/ui";
import { Text } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { formatNumberDisplay } from "@/shared/utils/number";
import { pluralize } from "@/shared/utils/string";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type {
  NumberPoolRange,
  NumberPoolUsage,
  NumberPoolUtilization,
} from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
  type NumberPoolType,
} from "@/entities/resource-manager/domain/model/pool";
import { NumberPoolUsageBar } from "@/entities/resource-manager/ui/number-pool/number-pool-usage-bar";

const ALL_RANGES_KEY = "all";

export const formatRangeLabel = ({ start, end }: Pick<NumberPoolRange, "start" | "end">) =>
  `${formatNumberDisplay(start.value)} – ${formatNumberDisplay(end.value)}`;

const getSelectedKeys = (utilization: NumberPoolUtilization, selectedRangeId: string | null) => {
  if (selectedRangeId === null) return [ALL_RANGES_KEY];
  return utilization.ranges.some(({ id }) => id === selectedRangeId) ? [selectedRangeId] : [];
};

interface RangeItem {
  id: string;
  title: string;
  subtitle: string;
  usage: NumberPoolUsage;
  href: string;
}

const getRangeItems = (poolId: string, utilization: NumberPoolUtilization): RangeItem[] => {
  const { ranges, usage } = utilization;

  return [
    {
      id: ALL_RANGES_KEY,
      title: "All ranges",
      subtitle: pluralize(ranges.length, "range"),
      usage,
      href: getObjectDetailsUrl(NUMBER_POOL_KIND, poolId),
    },
    ...ranges.map((range) => ({
      id: range.id,
      title: formatRangeLabel(range),
      subtitle: `Weight ${range.allocation_weight.value}`,
      usage: range.usage,
      href: getObjectDetailsUrl(NUMBER_POOL_KIND, poolId, undefined, `ranges/${range.id}`),
    })),
  ];
};

interface NoRangesCardProps {
  poolType: NumberPoolType;
}

function NoRangesCard({ poolType }: NoRangesCardProps) {
  return (
    <Card className="items-start gap-1 px-4 py-3 text-sm">
      <p className="font-medium">No ranges</p>
      <p className="text-pretty text-foreground-muted">
        This pool can't allocate numbers until it has a range.
      </p>
      <p className="text-foreground-muted">
        {poolType === NUMBER_POOL_TYPE_SCHEMA
          ? "Add one in the schema."
          : "Edit the pool to add one."}
      </p>
    </Card>
  );
}

export interface NumberPoolRangesCardProps {
  poolId: string;
  poolType: NumberPoolType;
  utilization: NumberPoolUtilization;
  selectedRangeId: string | null;
}

export function NumberPoolRangesCard({
  poolId,
  poolType,
  utilization,
  selectedRangeId,
}: NumberPoolRangesCardProps) {
  if (utilization.ranges.length === 0) {
    return <NoRangesCard poolType={poolType} />;
  }

  return (
    <Card className="shrink-0">
      <div className="px-3 pt-2 pb-1 font-medium text-foreground-muted text-sm">Ranges</div>
      <ListBox
        aria-label="Ranges"
        selectionMode="single"
        selectionIndicator="highlight"
        selectedKeys={getSelectedKeys(utilization, selectedRangeId)}
        items={getRangeItems(poolId, utilization)}
      >
        {(item) => (
          <ListBoxItem
            id={item.id}
            href={item.href}
            textValue={item.title}
            className="flex-col items-stretch gap-1.5 rounded-xl px-2.5 py-2"
          >
            <Row className="justify-between">
              <Text slot="label" className="font-medium tabular-nums">
                {item.title}
              </Text>
              <Text slot="description" className="text-foreground-muted text-xs">
                {item.subtitle}
              </Text>
            </Row>
            <NumberPoolUsageBar usage={item.usage} />
          </ListBoxItem>
        )}
      </ListBox>
    </Card>
  );
}
