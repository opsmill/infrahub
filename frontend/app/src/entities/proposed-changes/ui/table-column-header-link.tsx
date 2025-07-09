import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";
import { Button, ButtonProps } from "react-aria-components";

interface TableColumnHeaderLinkProps extends ButtonProps {
  isActive?: boolean;
}

export function TableColumnHeaderLink({
  children,
  className,
  isActive,
  ...props
}: TableColumnHeaderLinkProps) {
  return (
    <Button
      className={classNames(
        cellsStyle,
        cellHeaderStyle,
        "border-0 transition-all rounded-sm hover:bg-transparent hover:text-gray-500 font-normal",
        isActive && "font-semibold hover:text-black",
        className
      )}
      {...props}
    >
      <span className="truncate">{children}</span>
    </Button>
  );
}
