import {
  type ColumnDef,
  type ColumnOrderState,
  flexRender,
  getCoreRowModel,
  type RowSelectionOptions,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table";
import React from "react";

import { Row } from "@/shared/components/container";
import { StickyCellShadow } from "@/shared/components/table/sticky-cell-shadow";
import { COLUMN_MAX_WIDTH, cellFooterStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { ObjectTableSkeleton } from "@/entities/nodes/object/ui/object-table/object-table-skeleton";
import {
  type ObjectTableSelectionToolbarProps,
  ObjectTableToolbar,
} from "@/entities/nodes/object/ui/object-table/toolbar/object-table-toolbar";

export interface DataTableProps<T> extends React.HTMLAttributes<HTMLDivElement> {
  columnOrder?: ColumnOrderState;
  columns: ColumnDef<T>[];
  columnVisibility?: VisibilityState;
  count?: number;
  data: Array<T>;
  isLoading?: boolean;
  renderEmpty?: () => React.ReactNode;
  toolbarActions?: ObjectTableSelectionToolbarProps["renderMore"];
  enableRowSelection?: RowSelectionOptions<T>["enableRowSelection"];
  gridTemplateColumns?: (columnCount: number) => string;
}

/**
 * `fit-content` keeps short columns shrink-to-fit while capping long ones. A bare `auto` track has
 * no ceiling, so a single long value grows the column past the viewport — and because the first
 * column is sticky, it then paints over the row action menu and the horizontal scrollbar.
 *
 * The last two tracks belong to the identity and actions columns, so only the columns in between get
 * a capped track. `repeat()` requires a positive integer: with nothing in between, `repeat(0, …)`
 * makes the CSSOM reject the whole declaration — collapsing the grid to one implicit column and
 * splitting every row in two. Column visibility clamps to at least one field column, so this arm is
 * unreachable from the picker; it stays for any surface that builds its own column set.
 */
const defaultGridTemplateColumns = (columnCount: number) =>
  columnCount <= 2
    ? "1fr 2.5rem"
    : `repeat(${columnCount - 2}, fit-content(${COLUMN_MAX_WIDTH})) 1fr 2.5rem`;

export function DataTable<T extends NodeCore>({
  columnOrder,
  columns,
  columnVisibility,
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
      columnVisibility,
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

  // `min-w-max` stops the grid from being squeezed into its scroll container.
  // Without it the tracks compress until columns are unreadably narrow instead of
  // keeping their width and letting the table scroll horizontally.
  return (
    <div className="grid min-w-max content-start" style={style} {...props}>
      {allHeaders.map((header) => {
        return flexRender(header.column.columnDef.header, {
          ...header.getContext(),
          key: header.id,
        });
      })}

      {allRows.map((row) => {
        return (
          <div key={row.id} className="group contents" data-testid="data-table-row">
            {row.getVisibleCells().map((cell) => {
              return flexRender(cell.column.columnDef.cell, {
                ...cell.getContext(),
                key: cell.id,
              });
            })}
          </div>
        );
      })}

      {!isLoading && allRows.length === 0 && renderEmpty?.()}

      {isLoading && <ObjectTableSkeleton headerCount={allHeaders.length} />}

      {count !== undefined &&
        Array.from({ length: allHeaders.length }).map((_, index) => (
          <div
            key={index}
            // The whole footer bar has to outrank the sticky body cells, not just its
            // first cell, or the last row's sticky action menu punches through it.
            className={classNames(cellsStyle, cellFooterStyle, "z-10", index === 0 && "left-0")}
          >
            {index === 0 && (
              <>
                <Row className="gap-1">
                  <span className="font-medium">{formatNumberDisplay(count)}</span>
                  <span className="text-foreground-muted">count{count > 1 && "s"}</span>
                </Row>
                <StickyCellShadow side="left" />
              </>
            )}
          </div>
        ))}

      {selectedRows.length > 0 && (
        <ObjectTableToolbar
          selectedRows={selectedRows}
          onClose={table.resetRowSelection}
          renderMore={toolbarActions}
        />
      )}
    </div>
  );
}
