import {
  type ColumnDef,
  type ColumnOrderState,
  flexRender,
  getCoreRowModel,
  type RowSelectionOptions,
  useReactTable,
} from "@tanstack/react-table";
import React from "react";

import { Row } from "@/shared/components/container";
import { cellFooterStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

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
  count?: number;
  data: Array<T>;
  isLoading?: boolean;
  renderEmpty?: () => React.ReactNode;
  toolbarActions?: ObjectTableSelectionToolbarProps["renderMore"];
  enableRowSelection?: RowSelectionOptions<T>["enableRowSelection"];
  gridTemplateColumns?: (columnCount: number) => string;
}

const defaultGridTemplateColumns = (columnCount: number) =>
  `repeat(${columnCount - 2}, auto) 1fr 2.5rem`;

export function DataTable<T extends NodeCore>({
  columnOrder,
  columns,
  count,
  data,
  isLoading,
  renderEmpty,
  toolbarActions,
  enableRowSelection,
  gridTemplateColumns = defaultGridTemplateColumns,
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
      gridTemplateColumns: gridTemplateColumns(allHeaders.length),
    }),
    [allHeaders.length, gridTemplateColumns]
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

      {!!count &&
        Array.from({ length: allHeaders.length }).map((_, index) => (
          <div
            key={index}
            className={classNames(cellsStyle, cellFooterStyle, index === 0 && "left-0 z-10")}
          >
            {index === 0 && (
              <>
                <Row className="gap-1">
                  <span className="font-medium">{formatNumberDisplay(count)}</span>
                  <span className="text-gray-500">count{count && count > 1 && "s"}</span>
                </Row>
                <div className="pointer-events-none absolute top-0 -right-4 bottom-0 w-4 bg-linear-to-r from-gray-500/10" />
              </>
            )}
          </div>
        ))}
    </div>
  );
}
