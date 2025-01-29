import { cellBodyStyle, cellsStyle } from "@/entities/nodes/object/ui/objects-table/cells/style";
import { classNames } from "@/shared/utils/common";

export interface TableCellProps extends React.HTMLAttributes<HTMLDivElement> {}

export function TableCell({ className, ...props }: TableCellProps) {
  return <div className={classNames(cellsStyle, cellBodyStyle, className)} {...props} />;
}
