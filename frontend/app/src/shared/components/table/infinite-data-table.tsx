import { useAuth } from "@/entities/authentication/ui/useAuth";
import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";
import {
  ObjectTableSelectionToolbarProps,
  ObjectTableToolbar,
} from "@/entities/nodes/object/ui/object-table/toolbar/object-table-toolbar";
import { NodeObject } from "@/entities/nodes/types";
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import React from "react";

export interface InfiniteDataTableProps<T> extends React.HTMLAttributes<HTMLDivElement> {
  columns: ColumnDef<T>[];
  data: Array<T>;
  isLoading?: boolean;
  renderEmpty?: () => React.ReactNode;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  toolbarActions?: ObjectTableSelectionToolbarProps["renderMore"];
}

export function InfiniteDataTable<T extends NodeObject>({
  columns,
  data,
  isLoading,
  renderEmpty,
  hasNextPage,
  fetchNextPage,
  toolbarActions,
  ...props
}: InfiniteDataTableProps<T>) {
  const { isAuthenticated } = useAuth();
  const tableContainerRef = React.useRef<HTMLTableElement>(null);
  const table = useReactTable({
    columns,
    data,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    getRowId: (row) => row.id,
  });

  React.useEffect(() => {
    if (!isAuthenticated) {
      table.toggleAllRowsSelected(false);
    }
  }, [isAuthenticated]);

  const fetchMoreOnBottomReached = React.useCallback(
    (containerRefElement?: HTMLDivElement | null) => {
      if (containerRefElement) {
        const { scrollHeight, scrollTop, clientHeight } = containerRefElement;
        //once the user has scrolled within 250px of the bottom of the table, fetch more data if we can
        if (scrollHeight - scrollTop - clientHeight < 250 && !isLoading && hasNextPage) {
          fetchNextPage();
        }
      }
    },
    [fetchNextPage, isLoading]
  );

  React.useEffect(() => {
    fetchMoreOnBottomReached(tableContainerRef.current);
  }, [fetchMoreOnBottomReached]);

  const allHeaders = table.getFlatHeaders();
  const allRows = table.getRowModel().rows;
  const style = React.useMemo<React.CSSProperties>(
    () => ({
      gridTemplateColumns: `repeat(${allHeaders.length - 1}, minmax(auto, 1fr)) 2.5rem`,
    }),
    [allHeaders.length]
  );

  const selectedRows = table.getSelectedRowModel().flatRows.map((row) => row.original);

  return (
    <div
      className="grid content-start overflow-auto"
      style={style}
      onScroll={(e) => fetchMoreOnBottomReached(e.currentTarget)}
      ref={tableContainerRef}
      {...props}
    >
      {selectedRows.length > 0 && (
        <ObjectTableToolbar
          selectedRows={selectedRows}
          onClose={table.resetRowSelection}
          renderMore={toolbarActions}
        />
      )}

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

      {!isLoading && allRows.length === 0 && renderEmpty?.()}

      {isLoading && <ObjectTableSkeleton headerCount={allHeaders.length} />}
    </div>
  );
}
