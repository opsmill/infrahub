import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import {
  Cell as AriaCell,
  Column as AriaColumn,
  ColumnProps as AriaColumnProps,
  ResizableTableContainer as AriaResizableTableContainer,
  Row as AriaRow,
  Table as AriaTable,
  TableBody as AriaTableBody,
  TableHeader as AriaTableHeader,
  CellProps,
  ColumnResizer,
  Group,
  RowProps,
  TableBodyProps,
  TableHeaderProps,
  TableProps,
  composeRenderProps,
} from "react-aria-components";

export const ResizableTableContainer = AriaResizableTableContainer;

export const Table = ({ className, ...props }: TableProps) => (
  <AriaTable
    className={composeRenderProps(className, (className) =>
      classNames(
        "w-full caption-bottom text-sm -outline-offset-2 data-[focus-visible]:outline-ring",
        className
      )
    )}
    {...props}
  />
);

export const TableHeader = <T extends object>({ className, ...props }: TableHeaderProps<T>) => (
  <AriaTableHeader
    className={composeRenderProps(className, (className) =>
      classNames("[&_tr]:border-b", className)
    )}
    {...props}
  />
);

export interface ColumnProps extends AriaColumnProps {
  isResizable?: boolean;
}

export const TableColumn = ({ className, children, ...props }: ColumnProps) => (
  <AriaColumn
    className={composeRenderProps(className, (className) =>
      classNames(
        "h-12 text-left align-middle font-medium text-muted-foreground -outline-offset-2 data-[focus-visible]:outline-ring",
        className
      )
    )}
    {...props}
  >
    {composeRenderProps(children, (children, { allowsSorting }) => (
      <div className="flex items-center">
        <Group
          role="presentation"
          tabIndex={-1}
          className={classNames(
            "flex h-10 flex-1 items-center gap-1 overflow-hidden rounded-md px-4",
            allowsSorting && "p-2 data-[hovered]:bg-accent data-[hovered]:text-accent-foreground",
            "focus-visible:outline-none  data-[focus-visible]:-outline-offset-2 data-[focus-visible]:outline-ring [&:has([slot=selection])]:pr-0"
          )}
        >
          <span className="truncate">{children}</span>
          {allowsSorting && <Icon icon="mdi:arrow-down" className="ml-2 size-4" />}
        </Group>
        {props.isResizable && (
          <ColumnResizer className="data-[focus-visible]:ring-rin box-content h-5 w-px translate-x-[8px] cursor-col-resize rounded bg-muted-foreground bg-clip-content px-[8px]  py-1 focus-visible:outline-none data-[resizing]:w-[2px] data-[resizing]:bg-primary data-[resizing]:pl-[7px] data-[focus-visible]:ring-1  data-[focus-visible]:ring-ring" />
        )}
      </div>
    ))}
  </AriaColumn>
);

export const TableBody = <T extends object>({ className, ...props }: TableBodyProps<T>) => (
  <AriaTableBody
    className={composeRenderProps(className, (className) =>
      classNames(
        "-outline-offset-2 data-[empty]:h-24 data-[empty]:text-center data-[focus-visible]:outline-ring [&_tr:last-child]:border-0",
        className
      )
    )}
    {...props}
  />
);

export const TableRow = <T extends object>({ className, ...props }: RowProps<T>) => (
  <AriaRow
    className={composeRenderProps(className, (className) =>
      classNames(
        "border-b -outline-offset-2 transition-colors data-[hovered]:bg-muted/50 data-[selected]:bg-muted data-[focus-visible]:outline-ring",
        className
      )
    )}
    {...props}
  />
);

export const TableCell = ({ className, ...props }: CellProps) => (
  <AriaCell
    className={composeRenderProps(className, (className) =>
      classNames(
        "p-4 align-middle",
        "transition-colors data-[focused='true']:outline data-[focused='true']:outline-custom-blue-600",
        className
      )
    )}
    {...props}
  />
);
