import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";
import { useProposedChanges } from "@/entities/proposed-changes/api/get-proposed-changes.query";
import { ProposedChangesItem } from "@/entities/proposed-changes/ui/proposed-change-item";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";
import { ProposedChangesTableHeader } from "./proposed-changes-table-header";

type ProposedChangesTableProps = {};

export function ProposedChangesTable({
  schema,
  permission,
  baseFilters = [],
}: ProposedChangesTableProps) {
  const [filters] = useFilters();
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useProposedChanges({
    schema,
    filters: [...baseFilters, ...filters],
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

      {isLoading && <ObjectTableSkeleton headerCount={flatData.length} />}
    </InfiniteScroll>
  );
}
