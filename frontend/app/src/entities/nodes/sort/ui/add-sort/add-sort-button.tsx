import { Button, MenuTrigger, Popover, Tooltip } from "@infrahub/ui";
import { PlusIcon } from "lucide-react";

import {
  AddSortPicker,
  type AddSortPickerProps,
} from "@/entities/nodes/sort/ui/add-sort/add-sort-picker";
import { useSortableFields } from "@/entities/nodes/sort/ui/hooks/use-sortable-fields";

interface AddSortProps extends AddSortPickerProps {}

export function AddSortButton(props: AddSortProps) {
  const sortableFields = useSortableFields(props.schema);
  const noFieldsLeft = sortableFields.every(({ field }) => props.activeFields?.has(field));

  return (
    <MenuTrigger>
      <Tooltip message={noFieldsLeft ? "All fields are already in use." : undefined}>
        <Button
          variant="ghost"
          size="sm"
          className="justify-start text-foreground-muted"
          isDisabledAndFocusable={noFieldsLeft}
        >
          <PlusIcon />
          Add sort
        </Button>
      </Tooltip>

      <Popover placement="bottom start">
        <AddSortPicker {...props} />
      </Popover>
    </MenuTrigger>
  );
}
