import { classNames } from "@/shared/utils/common";
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
import { focusVisibleStyle } from "./style";

export const ResizableTableContainer = AriaResizableTableContainer;

export function Table({ className, ...props }: TableProps) {
  return (
    <AriaTable
      className={composeRenderProps(className, (className) =>
        classNames("w-full text-sm outline-none border-spacing-0", className)
      )}
      {...props}
    />
  );
}

export const TableHeader = <T extends object>({ ...props }: TableHeaderProps<T>) => (
  <AriaTableHeader {...props} />
);

export interface ColumnProps extends AriaColumnProps {}

export const TableColumn = ({ className, children, ...props }: ColumnProps) => (
  <AriaColumn
    className={composeRenderProps(className, (className) =>
      classNames("h-10 font-medium sticky top-0", className)
    )}
    {...props}
  >
    {composeRenderProps(children, (children) => (
      <div className="flex items-center border-y">
        <Group
          role="presentation"
          tabIndex={-1}
          className={classNames(
            focusVisibleStyle,
            "flex-grow flex items-center gap-1 h-10 overflow-hidden px-4 p-2 bg-stone-50",
            "data-[hovered]:bg-gray-100"
          )}
        >
          <span className="truncate">{children}</span>
        </Group>
        <ColumnResizer
          className={classNames(
            focusVisibleStyle,
            "h-10 w-px cursor-col-resize bg-gray-200 border-none",
            "data-[hovered]:bg-custom-blue-600",
            "data-[resizing]:bg-indigo-700 data-[resizing]:ring-2 data-[resizing]:ring-custom-blue-600/25"
          )}
        />
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
