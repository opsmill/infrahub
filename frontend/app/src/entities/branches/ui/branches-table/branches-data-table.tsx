import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import React from "react";

import { COLUMN_MAX_WIDTH, WIDE_COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchesToolbar } from "@/entities/branches/ui/branches-table/branches-toolbar";
import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";

export interface BranchesDataTableProps extends React.HTMLAttributes<HTMLDivElement> {
  columns: ColumnDef<BranchListItem>[];
  data: Array<BranchListItem>;
  isLoading?: boolean;
  renderEmpty?: () => React.ReactNode;
  gridTemplateColumns?: (columnCount: number) => string;
}

// Same capping rule as the shared DataTable: `fit-content` so short columns shrink
// to fit, with a ceiling so one long value cannot stretch the column off-screen.
const defaultGridTemplateColumns = (columnCount: number) =>
  [
    `fit-content(${WIDE_COLUMN_MAX_WIDTH})`,
    `fit-content(${COLUMN_MAX_WIDTH})`,
    "minmax(150px, 200px)",
    `repeat(${columnCount - 4}, fit-content(${COLUMN_MAX_WIDTH}))`,
    "2.5rem",
  ].join(" ");

export function BranchesDataTable({
  columns,
  data,
  isLoading,
  renderEmpty,
  gridTemplateColumns = defaultGridTemplateColumns,
  ...props
}: BranchesDataTableProps) {
  const { isAuthenticated } = useAuth();

  const table = useReactTable({
    columns,
    data,
    enableRowSelection: true,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    getRowId: (row) => row.id,
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
    // See DataTable: `min-w-max` keeps the columns at their own width and lets the
    // table scroll instead of compressing every track to fit the container.
    <div className="grid min-w-max content-start" style={style} {...props}>
      {selectedRows.length > 0 && (
        <BranchesToolbar selectedBranches={selectedRows} onClose={table.resetRowSelection} />
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
