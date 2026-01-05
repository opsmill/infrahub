import React from "react";

import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";

export const ObjectTable = () => {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useObjects({
    schema: selectedSchema,
    filters,
  });

  const columns = React.useMemo(() => {
    return [...getObjectTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  }, [selectedSchema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const isLoading = isPending || isFetchingNextPage;

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={flatData}
        isLoading={isLoading}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
        data-testid="object-items"
      />
    </InfiniteScroll>
  );
};
