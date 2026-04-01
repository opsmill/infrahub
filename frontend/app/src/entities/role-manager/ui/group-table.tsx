import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  GROUP_TABLE_ATTRIBUTES,
  GROUP_TABLE_RELATIONSHIPS,
  getGroupTableColumns,
} from "@/entities/role-manager/ui/get-group-table-columns";

export function GroupTable() {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters,
    getAttributesVisible: (attributes) =>
      attributes.filter((a) => GROUP_TABLE_ATTRIBUTES.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => GROUP_TABLE_RELATIONSHIPS.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [...getGroupTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  const rows = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={rows}
        count={count}
        isLoading={isPending || isFetchingNextPage}
      />
    </InfiniteScroll>
  );
}
