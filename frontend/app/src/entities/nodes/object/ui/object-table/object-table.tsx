import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";

export const ObjectTable = () => {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, error, hasNextPage, isPending, isFetchingNextPage } = useObjects(
    { schema: selectedSchema, filters },
    { enabled: count !== undefined }
  );

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [...getObjectTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  const flatData = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
        data-testid="object-items"
      />
    </InfiniteScroll>
  );
};
