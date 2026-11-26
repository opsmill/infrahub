import {
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableEmptyMessage,
  TableHeader,
  TableLink,
  TableLoadMoreItem,
  TableRow,
  TableSkeleton,
} from "@infrahub/ui";
import React from "react";
import { Collection } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type {
  NumberPoolDivisionSelector,
  NumberPoolRange,
} from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_PROVENANCE_PROVIDED,
  type NumberPoolAllocation,
  type NumberPoolProvenance,
} from "@/entities/resource-manager/domain/model/number-pool";
import { useNumberPoolAllocationFilters } from "@/entities/resource-manager/ui/hooks/use-number-pool-allocation-filters";
import { NumberPoolAllocationFiltersBar } from "@/entities/resource-manager/ui/number-pool/details/number-pool-allocation-filters-bar";
import { KindLabel } from "@/entities/resource-manager/ui/pool/kind-label";
import { PoolAllocationsError } from "@/entities/resource-manager/ui/pool/pool-allocations-error";
import { useGetNumberPoolAllocationCount } from "@/entities/resource-manager/ui/queries/get-number-pool-allocation-count.query";
import { useGetNumberPoolAllocations } from "@/entities/resource-manager/ui/queries/get-number-pool-allocations.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const allocationKey = ({ value, branch, holder }: NumberPoolAllocation) =>
  `${value}:${branch}:${holder.id}`;

interface SourceTagProps {
  provenance: NumberPoolProvenance;
}

function SourceTag({ provenance }: SourceTagProps) {
  const isProvided = provenance === NUMBER_POOL_PROVENANCE_PROVIDED;

  return (
    <span
      className={classNames(
        "inline-flex h-5 items-center rounded-md border px-1.5 font-medium text-xs",
        isProvided ? "border-active/40 text-active" : "border-border-strong text-foreground-muted"
      )}
    >
      {isProvided ? "Provided" : "Allocated"}
    </span>
  );
}

export interface NumberPoolAllocationsTableProps {
  poolId: string;
  nodeKind: string;
  nodeAttribute: string;
  ranges: NumberPoolRange[];
  selectedRange: NumberPoolRange | null;
  division?: NumberPoolDivisionSelector;
}

export function NumberPoolAllocationsTable({
  poolId,
  nodeKind,
  nodeAttribute,
  ranges,
  selectedRange,
  division,
}: NumberPoolAllocationsTableProps) {
  const titleId = React.useId();
  const [filters] = useNumberPoolAllocationFilters();
  const {
    data,
    error,
    isPending,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    isRefetchError,
    isRefetching,
    refetch,
  } = useGetNumberPoolAllocations({ poolId, rangeId: selectedRange?.id, division, filters });
  const { data: count } = useGetNumberPoolAllocationCount({
    poolId,
    rangeId: selectedRange?.id,
    division,
    filters,
  });
  const defaultBranch = useDefaultBranch();
  const { schema: nodeSchema } = useSchema(nodeKind);

  if (error && !data) return <ErrorScreen message={error.message} />;

  // a failed page must not be cancelled and restarted by the next scroll or retry
  const loadNextPage = () => fetchNextPage({ cancelRefetch: false });

  const defaultBranchName = defaultBranch?.name;
  const allocations = data?.pages.flat() ?? [];
  const showRangeColumn = selectedRange === null && ranges.length > 1;
  const rangeById = new Map(ranges.map((range) => [range.id, range]));
  const numberHeader =
    nodeSchema?.attributes?.find(({ name }) => name === nodeAttribute)?.label ?? "Number";
  const objectHeader = nodeSchema?.label ?? "Object";
  const isFiltered = filters.branch !== undefined || filters.provenance !== undefined;
  const rangeEmptyMessage = selectedRange
    ? `No allocations in ${selectedRange.display_label}`
    : "No allocations yet";
  const emptyMessage = isFiltered ? "No allocations match these filters" : rangeEmptyMessage;

  return (
    <Col className="min-h-0 min-w-0 flex-1 gap-0">
      <Row className="border-b px-3 py-2">
        <h2 id={titleId} className="font-semibold text-sm">
          Allocations
        </h2>
        {count !== undefined && (
          <span className="text-foreground-muted text-sm tabular-nums">
            {formatNumberDisplay(count)}
          </span>
        )}
        <NumberPoolAllocationFiltersBar />
      </Row>

      <Table aria-labelledby={titleId}>
        <TableHeader>
          <TableColumn isRowHeader>{numberHeader}</TableColumn>
          <TableColumn width="2fr">{objectHeader}</TableColumn>
          <TableColumn>Kind</TableColumn>
          <TableColumn>Branch</TableColumn>
          {showRangeColumn && <TableColumn>Range</TableColumn>}
          <TableColumn width={100}>Source</TableColumn>
        </TableHeader>

        <TableBody
          renderEmptyState={() =>
            isPending ? <TableSkeleton /> : <TableEmptyMessage>{emptyMessage}</TableEmptyMessage>
          }
        >
          <Collection
            items={allocations}
            dependencies={[showRangeColumn, defaultBranchName, ranges]}
          >
            {(allocation) => {
              const isDefaultBranch = allocation.branch === defaultBranchName;
              const range = rangeById.get(allocation.rangeId);
              const holderLabel = allocation.holder.display_label ?? allocation.holder.id;

              return (
                <TableRow id={allocationKey(allocation)}>
                  <TableCell>{formatNumberDisplay(allocation.value)}</TableCell>
                  <TableCell>
                    <TableLink
                      href={getObjectDetailsUrl(
                        allocation.holder.__typename,
                        allocation.holder.id,
                        [
                          isDefaultBranch
                            ? { name: QSP.BRANCH, exclude: true }
                            : { name: QSP.BRANCH, value: allocation.branch },
                        ]
                      )}
                    >
                      {holderLabel}
                    </TableLink>
                  </TableCell>
                  <TableCell>
                    <KindLabel kind={allocation.holder.__typename} />
                  </TableCell>
                  <TableCell>
                    <TableLink href={getBranchDetailsUrl(allocation.branch)}>
                      {allocation.branch}
                    </TableLink>
                  </TableCell>
                  {showRangeColumn && <TableCell>{range?.display_label}</TableCell>}
                  <TableCell>
                    <SourceTag provenance={allocation.provenance} />
                  </TableCell>
                </TableRow>
              );
            }}
          </Collection>
          {hasNextPage && !isFetchNextPageError && (
            <TableLoadMoreItem onLoadMore={loadNextPage} isLoading={isFetchingNextPage} />
          )}
        </TableBody>
      </Table>
      {isFetchNextPageError && (
        <PoolAllocationsError
          message="More allocations could not be loaded."
          isRetrying={isFetchingNextPage}
          onRetry={loadNextPage}
        />
      )}
      {isRefetchError && (
        <PoolAllocationsError
          message="The allocations could not be refreshed."
          isRetrying={isRefetching}
          onRetry={() => refetch()}
        />
      )}
    </Col>
  );
}
