import { Button, type ButtonProps } from "react-aria-components";

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
        "rounded-sm border-0 font-normal transition-all hover:bg-transparent hover:text-gray-500",
        isActive && "font-semibold hover:text-black",
        className
      )}
      {...props}
    />
  );
}
