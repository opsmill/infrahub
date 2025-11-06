import { useQueryState } from "nuqs";
import React from "react";
import { ListBox } from "react-aria-components";

import { QSP } from "@/config/qsp";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import type { Permission } from "@/entities/permission/types";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItem } from "@/entities/proposed-changes/ui/proposed-change-item";
import { ProposedChangesTableFilters } from "@/entities/proposed-changes/ui/proposed-changes-table-filters";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import type { NodeSchema } from "@/entities/schema/types";

import { computeProposedChangeFilters } from "../utils/compute-proposed-change-filters";

type ProposedChangesTableProps = {
  schema: NodeSchema;
  permission: Permission;
  hideFilters?: boolean;
  className?: string;
};

export function ProposedChangesTable({
  schema,
  hideFilters,
  className,
}: ProposedChangesTableProps) {
  const [proposedChangeState] = useQueryState(QSP.PROPOSED_CHANGES_STATE);

  const [filters] = useFilters();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useGetProposedChanges(
    {
      schema,
      filters: computeProposedChangeFilters({ filters, qsp: proposedChangeState as string }),
    }
  );

  const isLoading = isPending || isFetchingNextPage;

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage} className="h-full">
      {!hideFilters && <ProposedChangesTableFilters schema={schema} />}

      <ListBox
        aria-label="Branches list"
        items={flatData}
        className={classNames(
          "m-2 flex flex-col divide-y divide-gray-200 rounded-lg border border-gray-200",
          className
        )}
      >
        {flatData.map((node) => {
          return <ProposedChangesItem key={node.id} node={node} />;
        })}
      </ListBox>

      {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={schema} />}

      {isLoading && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
