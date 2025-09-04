import { Button, ButtonProps } from "react-aria-components";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

interface TableColumnHeaderLinkProps extends ButtonProps {
  isActive?: boolean;
}

export function ProposedChangeTableFilterLink({
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
    />
  );
}
