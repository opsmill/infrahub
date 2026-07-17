import { Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
import { CheckIcon } from "lucide-react";
import type React from "react";

import { Row } from "@/shared/components/container";

import type { Sort, SortDirection, SortField } from "@/entities/nodes/sort/domain/model/sort";
import { SortDirectionMenuItem } from "@/entities/nodes/sort/ui/sort-direction-menu-item";
import { DIRECTION_OPTIONS } from "@/entities/nodes/sort/ui/sort-options";

export interface SortableFieldMenuItemProps {
  field: SortField;
  icon?: React.ReactNode;
  label: string;
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
        <Row>
          {icon}
          {label}
          {activeDirection && (
            <>
              <CheckIcon className="ml-auto" />
              <span className="sr-only">active sort field</span>
            </>
          )}
        </Row>
      </MenuItem>

      <Popover>
        <Menu variant="picker" aria-label={`Sort direction for ${label}`}>
          {DIRECTION_OPTIONS.map((option) => (
            <SortDirectionMenuItem
              key={option.id}
              direction={option.id}
              isActive={activeDirection === option.id}
              onSelect={(direction) => onSelect({ field, direction })}
            >
              {option.label}
            </SortDirectionMenuItem>
          ))}
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}
