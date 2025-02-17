import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import React from "react";

export interface InfiniteDataTableProps<T> extends React.HTMLAttributes<HTMLDivElement> {
  columns: ColumnDef<T>[];
  data: Array<T>;
  isLoading?: boolean;
  ref?: React.Ref<HTMLDivElement>;
  renderEmpty?: () => React.ReactNode;
}

export function InfiniteDataTable<T extends object>({
  columns,
  data,
  isLoading,
  renderEmpty,
  ...props
}: InfiniteDataTableProps<T>) {
  const table = useReactTable({
    columns,
    data,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
  });

  const allHeaders = table.getFlatHeaders();
  const allRows = table.getRowModel().rows;
  const style = React.useMemo<React.CSSProperties>(
    () => ({
      gridTemplateColumns: `repeat(${allHeaders.length - 1}, minmax(auto, 1fr)) 2.5rem`,
    }),
    [allHeaders.length]
  );

  return (
    <div
      className="grid content-start overflow-auto"
      style={style}
      data-testid="object-items"
      {...props}
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

      {!isLoading && allRows.length === 0 && renderEmpty?.()}

      {isLoading && <ObjectTableSkeleton headerCount={allHeaders.length} />}
    </div>
  );
}
