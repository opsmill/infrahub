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
        "rounded-sm border-0 font-normal text-foreground-muted transition-all data-hovered:text-foreground",
        isActive && "font-semibold",
        className
      )}
      {...props}
    />
  );
}
