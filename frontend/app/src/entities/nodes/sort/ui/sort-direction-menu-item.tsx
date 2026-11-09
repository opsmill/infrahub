import { MenuItem } from "@infrahub/ui";
import { ArrowDownIcon, ArrowUpIcon, CheckIcon } from "lucide-react";

import { SORT_DIRECTION, type SortDirection } from "@/entities/nodes/sort/domain/model/sort";

export interface SortDirectionMenuItemProps {
  direction: SortDirection;
  onSelect: (direction: SortDirection) => void;
  isActive?: boolean;
  children: string;
}

export function SortDirectionMenuItem({
  direction,
  onSelect,
  isActive = false,
  children,
}: SortDirectionMenuItemProps) {
  return (
    <MenuItem id={direction} textValue={children} onAction={() => onSelect(direction)}>
      {direction === SORT_DIRECTION.DESC ? <ArrowDownIcon /> : <ArrowUpIcon />}
      <span>{children}</span>
      {isActive && (
        <>
          <CheckIcon className="ml-auto" />
          <span className="sr-only">active</span>
        </>
      )}
    </MenuItem>
  );
}
