import { QSP } from "@/config/qsp";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { Permission } from "@/entities/permission/types";
import { useProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { ProposedChangesItem } from "@/entities/proposed-changes/ui/proposed-change-item";
import { ProposedChangesTableHeader } from "@/entities/proposed-changes/ui/proposed-changes-table-header";
import { ProposedCHangesTableSkeleton } from "@/entities/proposed-changes/ui/proposed-changes-table-skeleton";
import { NodeSchema } from "@/entities/schema/types";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { computeFilters } from "../utils/computeFilters";

type ProposedChangesTableProps = {
  schema: NodeSchema;
  permission: Permission;
};

export function ProposedChangesTable({ schema }: ProposedChangesTableProps) {
  const [proposedChangeState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);

  const [filters] = useFilters();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useProposedChanges({
    schema,
    filters: computeFilters({ filters, state: proposedChangeState as string }),
  });

  const isLoading = isPending || isFetchingNextPage;

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <ProposedChangesTableHeader schema={schema} />

      {flatData.map((node) => {
        return <ProposedChangesItem key={node.id} node={node} />;
      })}

      {!isLoading && flatData.length === 0 && <ObjectTableEmpty schema={schema} />}

      {isLoading && <ProposedCHangesTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
