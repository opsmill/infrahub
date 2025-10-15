import { useQueryState } from "nuqs";
import React from "react";

import { QSP } from "@/config/qsp";

import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";

import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import type { Permission } from "@/entities/permission/types";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItem } from "@/entities/proposed-changes/ui/proposed-change-item";
import { ProposedChangesTableHeader } from "@/entities/proposed-changes/ui/proposed-changes-table-header";
import { ProposedChangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import type { NodeSchema } from "@/entities/schema/types";

import { computeProposedChangeFilters } from "../utils/compute-proposed-change-filters";

type ProposedChangesTableProps = {
  schema: NodeSchema;
  permission: Permission;
};

export function ProposedChangesTable({ schema }: ProposedChangesTableProps) {
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
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <ProposedChangesTableHeader schema={schema} />

      {flatData.map((node) => {
        return <ProposedChangesItem key={node.id} node={node} />;
      })}

      {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={schema} />}

      {isLoading && <ProposedChangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
