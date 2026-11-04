import { Card } from "@infrahub/ui";

import type {
  NumberPoolDivisionSelector,
  NumberPoolRange,
} from "@/entities/resource-manager/domain/model/number-pool";
import { NumberPoolAllocationsTable } from "@/entities/resource-manager/ui/number-pool/details/number-pool-allocations-table";
import { PoolItemNotFound } from "@/entities/resource-manager/ui/pool/pool-item-not-found";
import { getNumberPoolRangeUrl } from "@/entities/resource-manager/ui/routing/number-pool-urls";

export interface NumberPoolAllocationsCardProps {
  poolId: string;
  nodeKind: string;
  nodeAttribute: string;
  ranges: NumberPoolRange[];
  selectedRangeId: string | null;
  division?: NumberPoolDivisionSelector;
}

function AllocationsCardContent({
  selectedRangeId,
  ...tableProps
}: NumberPoolAllocationsCardProps) {
  if (selectedRangeId === null) {
    return <NumberPoolAllocationsTable key="all" {...tableProps} selectedRange={null} />;
  }

  const selectedRange = tableProps.ranges.find((range) => range.id === selectedRangeId);
  if (!selectedRange) {
    return (
      <PoolItemNotFound
        title="Range not found"
        description="The link points to a range this pool does not have. The range may have been deleted, or it may belong to another pool."
        href={getNumberPoolRangeUrl(tableProps.poolId)}
        linkLabel="View all ranges"
      />
    );
  }

  return (
    <NumberPoolAllocationsTable
      key={selectedRange.id}
      {...tableProps}
      selectedRange={selectedRange}
    />
  );
}

export function NumberPoolAllocationsCard(props: NumberPoolAllocationsCardProps) {
  if (props.ranges.length === 0) return null;

  return (
    <Card className="max-h-full grow overflow-hidden">
      <AllocationsCardContent {...props} />
    </Card>
  );
}
