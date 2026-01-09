import { Icon } from "@iconify-icon/react";

import { Checkbox, type CheckboxProps } from "@/shared/components/aria/checkbox";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";

interface BranchIdentifierHeaderProps extends CheckboxProps {
  className?: string;
}

export function BranchIdentifierHeader({ className, ...props }: BranchIdentifierHeaderProps) {
  const { isAuthenticated } = useAuth();

  return (
    <div
      className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white", className)}
    >
      {isAuthenticated && (
        <Checkbox aria-label="Select all branches" {...props} data-testid="select-all-rows" />
      )}
      <Icon icon="mdi:source-branch" className="text-stone-400" />
      <span className="truncate">Branch</span>
    </div>
  );
}
