import type React from "react";
import {
  Cell as AriaCell,
  type CellProps as AriaCellProps,
  Column as AriaColumn,
  type ColumnProps as AriaColumnProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
  Row as AriaRow,
  type RowProps as AriaRowProps,
  Table as AriaTable,
  TableBody as AriaTableBody,
  type TableBodyProps as AriaTableBodyProps,
  TableHeader as AriaTableHeader,
  type TableHeaderProps as AriaTableHeaderProps,
  TableLayout as AriaTableLayout,
  TableLoadMoreItem as AriaTableLoadMoreItem,
  type TableLoadMoreItemProps as AriaTableLoadMoreItemProps,
  type TableProps as AriaTableProps,
  Virtualizer as AriaVirtualizer,
  composeRenderProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

const ROW_HEIGHT = 36;
const HEADING_HEIGHT = 32;
const COLUMN_MIN_WIDTH = 120;
const SKELETON_WIDTHS = ["w-3/5", "w-4/5", "w-2/5"];
const SKELETON_HEIGHT = SKELETON_WIDTHS.length * ROW_HEIGHT;

const focusRingStyle =
  "outline-hidden data-focus-visible:rounded-md data-focus-visible:ring-1 data-focus-visible:ring-ring data-focus-visible:ring-inset";
const cellFocusRingStyle =
  "outline-hidden focus-within:rounded-md focus-within:ring-1 focus-within:ring-ring focus-within:ring-inset";

export interface TableProps extends AriaTableProps {}

export function Table({ className, style, ...props }: TableProps) {
  return (
    <AriaVirtualizer
      layout={AriaTableLayout}
      layoutOptions={{
        rowHeight: ROW_HEIGHT,
        headingHeight: HEADING_HEIGHT,
        loaderHeight: SKELETON_HEIGHT,
      }}
    >
      <AriaTable
        className={composeAriaClassName(
          className,
          cn(
            "relative min-h-0 w-full flex-1 overflow-auto overscroll-contain bg-table-cell",
            // an empty virtualized body is as tall as the table, so the table needs a height of its own
            "has-data-empty:min-h-(--table-empty-height)",
            // the virtualizer stacks every row and cell wrapper with an inline z-index, so a selected cell is lifted through them
            "[&_[role=rowgroup]>[role=presentation]:has(>[role=row]:focus-within)]:z-1!",
            "[&_[role=row]>[role=presentation]:has(>:focus-within)]:z-2!"
          )
        )}
        style={composeRenderProps(style, (resolvedStyle) => ({
          scrollPaddingTop: HEADING_HEIGHT,
          "--table-empty-height": `${HEADING_HEIGHT + SKELETON_HEIGHT}px`,
          ...resolvedStyle,
        }))}
        {...props}
      />
    </AriaVirtualizer>
  );
}

export interface TableHeaderProps<T> extends AriaTableHeaderProps<T> {}

export function TableHeader<T extends object>({ className, ...props }: TableHeaderProps<T>) {
  return (
    <AriaTableHeader
      // the virtualized header group has no height of its own, so without h-full its blur covers nothing
      className={composeAriaClassName(
        className,
        "h-full border-border/50 border-b backdrop-blur-sm"
      )}
      {...props}
    />
  );
}

export interface TableColumnProps extends AriaColumnProps {}

export function TableColumn({ className, width, minWidth, ...props }: TableColumnProps) {
  return (
    <AriaColumn
      width={width}
      minWidth={minWidth ?? (typeof width === "number" ? width : COLUMN_MIN_WIDTH)}
      className={composeAriaClassName(
        className,
        cn(
          "flex h-full items-center px-3 text-left font-medium text-foreground-muted text-xs",
          focusRingStyle
        )
      )}
      {...props}
    />
  );
}

export function TableSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading">
      {SKELETON_WIDTHS.map((width, index) => (
        <div
          key={index}
          className="flex items-center border-border/50 border-b px-3"
          style={{ height: ROW_HEIGHT }}
        >
          <div className={cn("h-3 animate-skeleton rounded-md bg-content-strong", width)} />
        </div>
      ))}
    </div>
  );
}

export interface TableEmptyMessageProps {
  children: React.ReactNode;
}

export function TableEmptyMessage({ children }: TableEmptyMessageProps) {
  return (
    <div
      className="flex items-center justify-center gap-2 text-foreground-muted text-sm"
      style={{ height: SKELETON_HEIGHT }}
    >
      {children}
    </div>
  );
}

export interface TableBodyProps<T> extends AriaTableBodyProps<T> {}

export function TableBody<T extends object>(props: TableBodyProps<T>) {
  return <AriaTableBody {...props} />;
}

export interface TableRowProps<T> extends AriaRowProps<T> {}

export function TableRow<T extends object>({ className, ...props }: TableRowProps<T>) {
  return (
    <AriaRow
      // the virtualizer leaves rows 1px tall and sets data-hovered only on rows with an action
      className={composeAriaClassName(
        className,
        cn(
          "h-full border-border/50 border-b transition-colors duration-100 hover:bg-content-muted",
          focusRingStyle
        )
      )}
      {...props}
    />
  );
}

// a selected cell grows over its neighbours to show its full value, so it needs an opaque background to hide them
const expandedCellStyle = cn(
  "focus-within:h-auto focus-within:min-h-full focus-within:w-max focus-within:min-w-full focus-within:max-w-md focus-within:py-2",
  "focus-within:data-truncated:bg-table-cell-raised focus-within:data-truncated:shadow-lg",
  "focus-within:data-grows-left:absolute focus-within:data-grows-left:right-0",
  "focus-within:data-grows-up:absolute focus-within:data-grows-up:bottom-0"
);

function growsBack(size: number, roomAhead: number, roomBehind: number) {
  return size > roomAhead && roomBehind > roomAhead;
}

function measureExpansion(cell: HTMLElement) {
  const slot = cell.parentElement;
  const table = cell.closest("[role=grid]");
  if (!slot || !table) return;

  const slotBox = slot.getBoundingClientRect();
  const tableBox = table.getBoundingClientRect();
  const width = cell.offsetWidth;
  const height = cell.offsetHeight;

  cell.toggleAttribute("data-truncated", width > slot.clientWidth || height > slot.clientHeight);
  cell.toggleAttribute(
    "data-grows-left",
    growsBack(width, tableBox.right - slotBox.left, slotBox.right - tableBox.left)
  );
  cell.toggleAttribute(
    "data-grows-up",
    growsBack(height, tableBox.bottom - slotBox.top, slotBox.bottom - tableBox.top - HEADING_HEIGHT)
  );
}

function trackExpansion(content: HTMLElement | null) {
  const cell = content?.parentElement;
  if (!cell) return;

  const measure = () => measureExpansion(cell);
  cell.addEventListener("focusin", measure);
  return () => cell.removeEventListener("focusin", measure);
}

function getPlainText(content: unknown) {
  if (typeof content === "string" || typeof content === "number") return String(content);

  return;
}

export interface TableCellProps extends AriaCellProps {}

export function TableCell({ className, children, textValue, ...props }: TableCellProps) {
  return (
    <AriaCell
      textValue={textValue ?? getPlainText(children)}
      className={composeAriaClassName(
        className,
        cn(
          "group/cell flex h-full min-w-0 items-center px-3 text-foreground-muted text-sm tabular-nums",
          "[&[role=rowheader]]:font-medium",
          cellFocusRingStyle,
          expandedCellStyle
        )
      )}
      {...props}
    >
      {composeRenderProps(children, (resolvedChildren) => (
        <div
          ref={trackExpansion}
          className="group-focus-within/cell:wrap-anywhere min-w-0 truncate group-focus-within/cell:whitespace-normal"
        >
          {resolvedChildren}
        </div>
      ))}
    </AriaCell>
  );
}

export interface TableLinkProps extends AriaLinkProps {}

export function TableLink({ className, ...props }: TableLinkProps) {
  return (
    <AriaLink
      className={composeAriaClassName(
        className,
        "text-foreground underline-offset-4 outline-hidden data-hovered:underline"
      )}
      {...props}
    />
  );
}

export interface TableLoadMoreItemProps extends Omit<AriaTableLoadMoreItemProps, "children"> {}

export function TableLoadMoreItem(props: TableLoadMoreItemProps) {
  return (
    <AriaTableLoadMoreItem {...props}>
      <TableSkeleton />
    </AriaTableLoadMoreItem>
  );
}
