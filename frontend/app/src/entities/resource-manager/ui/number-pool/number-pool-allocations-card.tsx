import { Card, LinkButton } from "@infrahub/ui";
import { SearchXIcon } from "lucide-react";

import { Col } from "@/shared/components/container";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { NumberPoolRange } from "@/entities/resource-manager/domain/model/number-pool";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";
import { NumberPoolAllocationsTable } from "@/entities/resource-manager/ui/number-pool/number-pool-allocations-table";

interface UnknownRangeProps {
  poolId: string;
}

function UnknownRange({ poolId }: UnknownRangeProps) {
  return (
    <Col className="items-center gap-4 px-6 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-content-muted text-foreground-muted">
        <SearchXIcon className="size-5" aria-hidden />
      </span>
      <Col className="max-w-sm items-center gap-1.5">
        <p className="font-medium">Range not found</p>
        <p className="text-pretty text-foreground-muted text-sm">
          The link points to a range this pool does not have. The range may have been deleted, or it
          may belong to another pool.
        </p>
      </Col>
      <LinkButton variant="outline" size="sm" href={getObjectDetailsUrl(NUMBER_POOL_KIND, poolId)}>
        View all ranges
      </LinkButton>
    </Col>
  );
}

export interface NumberPoolAllocationsCardProps {
  poolId: string;
  nodeKind: string;
  nodeAttribute: string;
  ranges: NumberPoolRange[];
  selectedRangeId: string | null;
}

function AllocationsCardContent({
  selectedRangeId,
  ...tableProps
}: NumberPoolAllocationsCardProps) {
  if (selectedRangeId === null) {
    return <NumberPoolAllocationsTable key="all" {...tableProps} selectedRange={null} />;
  }

  const selectedRange = tableProps.ranges.find((range) => range.id === selectedRangeId);
  if (!selectedRange) return <UnknownRange poolId={tableProps.poolId} />;

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
