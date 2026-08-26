import { StickyCellShadow } from "@/shared/components/table/sticky-cell-shadow";
import { cellMutedStyle } from "@/shared/components/table/style";
import { TableCell, type TableCellProps } from "@/shared/components/table/table-cell";
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
      className={classNames(
        "sticky left-0 z-1 font-medium",
        isMuted ? cellMutedStyle : "bg-table-cell-pinned",
        className
      )}
      {...props}
    >
      {children}
      <StickyCellShadow side="left" />
    </TableCell>
  );
}

export function StickyRightCell({ className, isMuted, children, ...props }: StickyCellProps) {
  return (
    <TableCell
      className={classNames(
        "sticky right-0 -ml-px size-10 items-center justify-center border-l",
        isMuted ? cellMutedStyle : "bg-table-cell-pinned",
        className
      )}
      {...props}
    >
      <StickyCellShadow side="right" />
      {children}
    </TableCell>
  );
}
