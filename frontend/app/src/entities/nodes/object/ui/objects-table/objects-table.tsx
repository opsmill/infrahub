import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { ObjectTableNoResults } from "@/entities/nodes/object/ui/objects-table/object-table-no-results";
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

export const ObjectsTable = ({ schema }: { schema: IModelSchema }) => {
  const tableContainerRef = React.useRef<HTMLTableElement>(null);
  const [filters] = useFilters();
  const { isPending, data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery(
    getObjectsInfiniteQueryOptions({ schema, filters })
  );

  const columns = React.useMemo(() => getObjectTableColumns(schema), [schema.hash]);
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
      className="grid content-start h-[calc(100vh-14rem)] overflow-auto"
      onScroll={(e) => fetchMoreOnBottomReached(e.currentTarget)}
      ref={tableContainerRef}
      style={{
        gridTemplateColumns: `repeat(${allHeaders.length - 1}, 1fr) 40px`,
      }}
      data-testid="object-items"
    >
      {allHeaders.map((header) => {
        return flexRender(header.column.columnDef.header, header.getContext());
      })}

      {allRows.map((row) => {
        return row.getAllCells().map((cell) => {
          return flexRender(cell.column.columnDef.cell, cell.getContext());
        });
      })}

      {!(isPending || isFetchingNextPage) && allRows.length === 0 && (
        <ObjectTableNoResults schema={schema} />
      )}

      {(isPending || isFetchingNextPage) && (
        <>
          {[...Array(15)].map((_, rowIndex) => (
            <React.Fragment key={`skeleton-row-${rowIndex}`}>
              {[...Array(allHeaders.length)].map((_, colIndex) => (
                <TableCell
                  key={`skeleton-${rowIndex}-${colIndex}`}
                  className={classNames(colIndex === 0 && "sticky left-0")}
                >
                  <Skeleton className="h-4 w-full" />
                </TableCell>
              ))}
            </React.Fragment>
          ))}
        </>
      )}
    </div>
  );
};
