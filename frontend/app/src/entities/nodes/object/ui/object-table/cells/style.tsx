import { cellMutedStyle } from "@/shared/components/table/style";
import { TableCell, TableCellProps } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

export interface StickyCellProps extends TableCellProps {
  isMuted?: boolean;
}

export function StickyLeftCell({
  className,
  isMuted = false,
  children,
  ...props
}: StickyCellProps) {
  return (
    <TableCell
      className={classNames("sticky left-0 z-1", isMuted ? cellMutedStyle : "bg-white", className)}
      {...props}
    >
      {children}
      <div className="absolute -right-4 top-0 bottom-0 w-4 bg-linear-to-r from-gray-500/10 pointer-events-none" />
    </TableCell>
  );
}

export function StickyRightCell({ className, isMuted, children, ...props }: StickyCellProps) {
  return (
    <TableCell
      className={classNames(
        "sticky right-0 border-l size-10 items-center justify-center -ml-px",
        isMuted ? cellMutedStyle : "bg-white",
        className
      )}
      {...props}
    >
      <div className="absolute -left-4 top-0 bottom-0 w-4 bg-linear-to-r from-transparent to-gray-300/30 pointer-events-none" />
      {children}
    </TableCell>
  );
}
