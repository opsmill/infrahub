import { cellBodyStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

export interface TableCellProps extends React.HTMLAttributes<HTMLDivElement> {}

export function TableCell({ className, ...props }: TableCellProps) {
  return <div className={classNames(cellsStyle, cellBodyStyle, className)} {...props} />;
}
