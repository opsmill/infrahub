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
      className={classNames("sticky left-0 z-1", isMuted ? cellMutedStyle : "bg-white", className)}
      {...props}
    >
      {children}
      <div className="-right-4 pointer-events-none absolute top-0 bottom-0 w-4 bg-gradient-to-r from-gray-500/10" />
    </TableCell>
  );
}

export function StickyRightCell({ className, isMuted, children, ...props }: StickyCellProps) {
  return (
    <TableCell
      className={classNames(
        "-ml-px sticky right-0 size-10 items-center justify-center border-l",
        isMuted ? cellMutedStyle : "bg-white",
        className
      )}
      {...props}
    >
      <div className="-left-4 pointer-events-none absolute top-0 bottom-0 w-4 bg-gradient-to-r from-transparent to-gray-300/30" />
      {children}
    </TableCell>
  );
}
