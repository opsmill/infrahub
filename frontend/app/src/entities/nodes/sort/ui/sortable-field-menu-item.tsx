import { Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
import { ArrowDownIcon, ArrowUpIcon, CheckIcon } from "lucide-react";
import type React from "react";

import {
  SORT_DIRECTION,
  type Sort,
  type SortDirection,
  type SortField,
} from "@/entities/nodes/sort/domain/model/sort";
import { DIRECTION_OPTIONS } from "@/entities/nodes/sort/ui/sort-options";

export interface SortableFieldMenuItemProps {
  field: SortField;
  icon?: React.ReactNode;
  label: string;
  /** Direction of the active sort when this field drives it. */
  activeDirection?: SortDirection;
  onSelect: (sort: Sort) => void;
}

export function SortableFieldMenuItem({
  field,
  icon,
  label,
  activeDirection,
  onSelect,
}: SortableFieldMenuItemProps) {
  return (
    <SubmenuTrigger>
      <MenuItem textValue={label}>
        {icon}
        <span>{label}</span>
        {activeDirection && (
          <>
            <CheckIcon className="ml-auto" />
            <span className="sr-only">active sort field</span>
          </>
        )}
      </MenuItem>

      <Popover>
        <Menu variant="picker" aria-label={`Sort direction for ${label}`} items={DIRECTION_OPTIONS}>
          {(option) => (
            <MenuItem
              textValue={option.label}
              onAction={() => onSelect({ field, direction: option.id })}
            >
              {option.id === SORT_DIRECTION.DESC ? <ArrowDownIcon /> : <ArrowUpIcon />}
              <span>{option.label}</span>
              {activeDirection === option.id && (
                <>
                  <CheckIcon className="ml-auto" />
                  <span className="sr-only">active</span>
                </>
              )}
            </MenuItem>
          )}
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}
