import { useQueryState } from "nuqs";
import React from "react";
import { ListBox } from "react-aria-components";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { QSP } from "@/shared/config/qsp";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { useGetProposedChanges } from "@/entities/proposed-changes/ui/queries/get-proposed-changes.query";
import { ProposedChangesItem } from "@/entities/proposed-changes/ui/proposed-change-item";
import { ProposedChangesTableFilters } from "@/entities/proposed-changes/ui/proposed-changes-table-filters";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import { computeProposedChangeFilters } from "@/entities/proposed-changes/utils/compute-proposed-change-filters";
import type { NodeSchema } from "@/entities/schema/types";

type ProposedChangesTableProps = {
  schema: NodeSchema;
  className?: string;
};

export function ProposedChangesTable({ schema, className }: ProposedChangesTableProps) {
  const [proposedChangeState] = useQueryState(QSP.PROPOSED_CHANGES_STATE);

  const [filters] = useFilters();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useGetProposedChanges(
    {
      schema,
      filters: computeProposedChangeFilters({ filters, qsp: proposedChangeState as string }),
    }
  );

  const isLoading = isPending || isFetchingNextPage;

  const flatData = React.useMemo(() => data?.pages?.flatMap((page) => page.items) ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage} className="h-full">
      <ProposedChangesTableFilters schema={schema} />

      <ListBox
        aria-label="Branches list"
        items={flatData}
        className={classNames(
          "m-2 flex flex-col divide-y divide-gray-200 rounded-lg border border-gray-200",
          className
        )}
      >
        {(proposedChange) => (
          <ProposedChangesItem key={proposedChange.id} proposedChange={proposedChange} />
        )}
      </ListBox>

      {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={schema} />}

      {isLoading && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
