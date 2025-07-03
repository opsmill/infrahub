import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { ObjectsTableProps } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getProposedChangesTableColumns } from "@/entities/proposed-changes/utils/get-proposed-changes-table-columns";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import React from "react";

const PROPOSED_CHANGES_TABLE_COLUMN_ORDER = ["id", "name"];

export interface ProposedChangesTableProps extends ObjectsTableProps {
  baseFilters?: Array<Filter>;
}

export function ProposedChangesTable({
  schema,
  permission,
  baseFilters = [],
}: ProposedChangesTableProps) {
  const [filters] = useFilters();
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useObjects({
    schema,
    filters: [...baseFilters, ...filters],
  });

  const columns = React.useMemo(() => {
    return [...getProposedChangesTableColumns(schema), getObjectActionsColumn(permission)];
  }, [schema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={PROPOSED_CHANGES_TABLE_COLUMN_ORDER}
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={schema} />}
        data-testid="ip-prefix-table"
      />
    </InfiniteScroll>
  );
}
