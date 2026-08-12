import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  getRoleTableColumns,
  ROLE_TABLE_ATTRIBUTES,
  ROLE_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-role-table-columns";

export function RoleTable() {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters,
    getAttributesVisible: (attributes) =>
      attributes.filter((a) => ROLE_TABLE_ATTRIBUTES.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => ROLE_TABLE_RELATIONSHIPS.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [...getRoleTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  const rows = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={rows}
        count={count}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
      />
    </InfiniteScroll>
  );
}
