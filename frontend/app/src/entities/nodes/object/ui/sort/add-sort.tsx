import {
  Autocomplete,
  Button,
  Menu,
  MenuItem,
  MenuTrigger,
  Popover,
  SubmenuTrigger,
  Tooltip,
} from "@infrahub/ui";
import { PlusIcon } from "lucide-react";

import type { Sort } from "@/entities/nodes/object/domain/sort";
import type { SortableField, SortDirection } from "@/entities/nodes/object/domain/sortable-field";

interface AddSortProps {
  fields: SortableField[];
  onAdd: (sort: Sort) => void;
}

export function AddSort({ fields, onAdd }: AddSortProps) {
  const noFieldsLeft = fields.length === 0;

  return (
    <MenuTrigger>
      <Tooltip message={noFieldsLeft ? "All fields are already in use." : undefined}>
        <Button
          variant="ghost"
          size="sm"
          className="justify-start text-stone-600"
          isDisabledAndFocusable={noFieldsLeft}
        >
          <PlusIcon />
          Add sort
        </Button>
      </Tooltip>

      <Popover placement="bottom start">
        <AddSortPicker fields={fields} onSelect={onAdd} />
      </Popover>
    </MenuTrigger>
  );
}

export const DIRECTION_OPTIONS: { id: SortDirection; label: string }[] = [
  { id: "ASC", label: "Ascending" },
  { id: "DESC", label: "Descending" },
];

interface AddSortPickerProps {
  fields: SortableField[];
  onSelect: (sort: Sort) => void;
}

export function AddSortPicker({ fields, onSelect }: AddSortPickerProps) {
  return (
    <Autocomplete>
      <Menu variant="picker" aria-label="Add sort field" className="max-h-72" items={fields}>
        {(field) => (
          <SubmenuTrigger>
            <MenuItem textValue={field.label}>{field.label}</MenuItem>

            <Popover>
              <Menu
                aria-label={`Sort direction for ${field.label}`}
                items={DIRECTION_OPTIONS}
                onAction={(_, value) => onSelect({ field: field.field, direction: value.id })}
              >
                {(direction) => (
                  <MenuItem id={direction.id} textValue={direction.label}>
                    {direction.label}
                  </MenuItem>
                )}
              </Menu>
            </Popover>
          </SubmenuTrigger>
        )}
      </Menu>
    </Autocomplete>
  );
}
