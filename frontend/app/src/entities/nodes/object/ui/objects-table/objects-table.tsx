import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { ObjectTableNoResults } from "@/entities/nodes/object/ui/objects-table/object-table-no-results";
import { Permission } from "@/entities/permission/types";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { Skeleton } from "@/shared/components/skeleton";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import React from "react";
import { getObjectTableColumns } from "./get-object-table-columns";

export const ObjectsTable = ({
  schema,
  permission,
}: { schema: IModelSchema; permission: Permission }) => {
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

  const table = useReactTable({
    columns,
    data: flatData,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
  });

  const allHeaders = table.getFlatHeaders();
  const allRows = table.getRowModel().rows;

  return (
    <div
      className="grid content-start overflow-auto"
      onScroll={(e) => fetchMoreOnBottomReached(e.currentTarget)}
      ref={tableContainerRef}
      style={{
        gridTemplateColumns: `repeat(${allHeaders.length - 1}, minmax(auto, 1fr)) 2.5rem`,
      }}
      data-testid="object-items"
    >
      {allHeaders.map((header) => {
        return flexRender(header.column.columnDef.header, {
          ...header.getContext(),
          key: header.id,
        });
      })}

      {allRows.map((row) => {
        return row.getVisibleCells().map((cell) => {
          return flexRender(cell.column.columnDef.cell, {
            ...cell.getContext(),
            key: cell.id,
          });
        });
      })}

      {!(isPending || isFetchingNextPage) && allRows.length === 0 && (
        <ObjectTableNoResults schema={schema} />
      )}

      {(isPending || isFetchingNextPage) && <ObjectTableSkeleton headerCount={allHeaders.length} />}
    </div>
  );
};
