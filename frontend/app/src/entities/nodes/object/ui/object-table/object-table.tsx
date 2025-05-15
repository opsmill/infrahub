import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";
import { getObjectTableColumns } from "./get-object-table-columns";

export interface ObjectsTableProps {
  schema: ModelSchema;
  permission: Permission;
}

export const ObjectTable = ({ schema, permission }: ObjectsTableProps) => {
  const [filters] = useFilters();
  const { isFetching, data, fetchNextPage, hasNextPage } = useObjects({ schema, filters });

  const columns = React.useMemo(() => {
    return [...getObjectTableColumns(schema), getObjectActionsColumn(permission)];
  }, [schema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={flatData}
        isLoading={isFetching}
        renderEmpty={() => <ObjectTableEmpty schema={schema} />}
        data-testid="object-items"
      />
    </InfiniteScroll>
  );
};
