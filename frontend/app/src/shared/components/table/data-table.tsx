import {
  type ColumnDef,
  type ColumnOrderState,
  flexRender,
  getCoreRowModel,
  type RowSelectionOptions,
  useReactTable,
} from "@tanstack/react-table";
import React from "react";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";
import {
  type ObjectTableSelectionToolbarProps,
  ObjectTableToolbar,
} from "@/entities/nodes/object/ui/object-table/toolbar/object-table-toolbar";
import type { NodeCore } from "@/entities/nodes/types";

export interface DataTableProps<T> extends React.HTMLAttributes<HTMLDivElement> {
  columnOrder?: ColumnOrderState;
  columns: ColumnDef<T>[];
  data: Array<T>;
  isLoading?: boolean;
  renderEmpty?: () => React.ReactNode;
  toolbarActions?: ObjectTableSelectionToolbarProps["renderMore"];
  enableRowSelection?: RowSelectionOptions<T>["enableRowSelection"];
}

export function DataTable<T extends NodeCore>({
  columnOrder,
  columns,
  data,
  isLoading,
  renderEmpty,
  toolbarActions,
  enableRowSelection,
  ...props
}: DataTableProps<T>) {
  const { isAuthenticated } = useAuth();

  const table = useReactTable({
    columns,
    data,
    enableRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    getRowId: (row) => row.id,
    state: {
      columnOrder,
    },
  });

  React.useEffect(() => {
    if (!isAuthenticated) {
      table.toggleAllRowsSelected(false);
    }
  }, [isAuthenticated]);

  const allHeaders = table.getFlatHeaders();
  const allRows = table.getRowModel().rows;
  const style = React.useMemo<React.CSSProperties>(
    () => ({
      gridTemplateColumns: `repeat(${allHeaders.length - 2}, auto) 1fr 2.5rem`,
    }),
    [allHeaders.length]
  );

  const selectedRows = table.getSelectedRowModel().flatRows.map((row) => row.original);

  return (
    <div className="grid content-start" style={style} {...props}>
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
