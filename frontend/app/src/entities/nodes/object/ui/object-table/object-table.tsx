import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { Permission } from "@/entities/permission/types";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { InfiniteDataTable } from "@/shared/components/table/infinite-data-table";
import useFilters from "@/shared/hooks/useFilters";
import { useInfiniteQuery } from "@tanstack/react-query";
import React from "react";
import { getObjectTableColumns } from "./get-object-table-columns";

export interface ObjectsTableProps {
  schema: IModelSchema;
  permission: Permission;
}

export const ObjectTable = ({ schema, permission }: ObjectsTableProps) => {
  const tableContainerRef = React.useRef<HTMLTableElement>(null);
  const [filters] = useFilters();
  const { isPending, data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery(
    getObjectsInfiniteQueryOptions({ schema, filters })
  );

  const columns = React.useMemo(() => getObjectTableColumns(schema, permission), [schema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const fetchMoreOnBottomReached = React.useCallback(
    (containerRefElement?: HTMLDivElement | null) => {
      if (containerRefElement) {
        const { scrollHeight, scrollTop, clientHeight } = containerRefElement;
        //once the user has scrolled within 250px of the bottom of the table, fetch more data if we can
        if (scrollHeight - scrollTop - clientHeight < 250 && !isFetchingNextPage && hasNextPage) {
          fetchNextPage();
        }
      }
    },
    [fetchNextPage, isFetchingNextPage, hasNextPage]
  );

  React.useEffect(() => {
    fetchMoreOnBottomReached(tableContainerRef.current);
  }, [fetchMoreOnBottomReached]);

  return (
    <InfiniteDataTable
      columns={columns}
      data={flatData}
      isLoading={isPending || isFetchingNextPage}
      onScroll={(e) => fetchMoreOnBottomReached(e.currentTarget)}
      ref={tableContainerRef}
      renderEmpty={() => <ObjectTableEmpty schema={schema} />}
    />
  );
};
