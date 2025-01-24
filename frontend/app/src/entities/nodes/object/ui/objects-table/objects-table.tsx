import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { ObjectFilterDisplay } from "@/entities/nodes/object/ui/objects-table/filtering/object-filter-display";
import { ObjectFilterResetButton } from "@/entities/nodes/object/ui/objects-table/filtering/object-filter-reset-button";
import { ObjectSearchInput } from "@/entities/nodes/object/ui/objects-table/filtering/object-search-input";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { Spinner } from "@/shared/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import useFilters from "@/shared/hooks/useFilters";
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
        //once the user has scrolled within 300px of the bottom of the table, fetch more data if we can
        if (scrollHeight - scrollTop - clientHeight < 300 && !isFetchingNextPage && hasNextPage) {
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
    debugTable: true,
  });

  return (
    <div
      className="overflow-auto max-h-[calc(100vh-10.5rem)]"
      onScroll={(e) => fetchMoreOnBottomReached(e.currentTarget)}
      ref={tableContainerRef}
    >
      <div className="flex items-center gap-2 p-2">
        <ObjectSearchInput schema={schema} loading={isPending} />

        {filters.map((filter) => (
          <ObjectFilterDisplay key={filter.name} filter={filter} schema={schema} />
        ))}

        {filters.length > 0 && <ObjectFilterResetButton />}
      </div>

      <Table>
        <TableHeader columns={table.getFlatHeaders()}>
          {(header) => {
            const { column } = header;
            const isPinned = header.id === "id";

            return (
              <TableColumn
                isRowHeader
                className="sticky top-0 bg-stone-50"
                style={{
                  width: column.getSize(),
                  left: isPinned ? `${column.getStart("left")}px` : undefined,
                  zIndex: isPinned ? 2 : undefined,
                }}
              >
                {header.isPlaceholder
                  ? null
                  : flexRender(column.columnDef.header, header.getContext())}
              </TableColumn>
            );
          }}
        </TableHeader>

        <TableBody items={table.getRowModel().rows} renderEmptyState={() => "No results."}>
          {(row) => (
            <TableRow columns={row.getVisibleCells()}>
              {(cell) => {
                const { column } = cell;
                const isPinned = column.id === "id";

                return (
                  <TableCell
                    className="bg-white"
                    style={{
                      width: column.getSize(),
                      position: isPinned ? "sticky" : undefined,
                      left: isPinned ? `${column.getStart("left")}px` : undefined,
                      zIndex: isPinned ? 1 : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              }}
            </TableRow>
          )}
        </TableBody>
      </Table>
      {isFetchingNextPage && <Spinner />}
    </div>
  );
};
