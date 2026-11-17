import { Tooltip } from "@infrahub/ui";

import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";

import type { PcActionAvailability } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";

export interface PcActionComboboxItem<TValue extends string> {
  value: TValue;
  name: string;
  /** Without it the item is always selectable. */
  availability?: PcActionAvailability;
}

interface PcActionComboboxListProps<TValue extends string> {
  items: PcActionComboboxItem<TValue>[];
  value?: TValue | null;
  onSelect: (value: TValue) => void;
}

export function PcActionComboboxList<TValue extends string>({
  items,
  value,
  onSelect,
}: PcActionComboboxListProps<TValue>) {
  return (
    <ComboboxList>
      {items.map((item) => {
        if (item.availability && !item.availability.available) {
          return (
            <Tooltip
              message={item.availability.unavailability_reason}
              className="whitespace-pre"
              key={item.value}
              nonInteractiveTrigger
            >
              <span className="ml-5 flex cursor-default select-none items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm opacity-50 outline-hidden">
                {item.name}
              </span>
            </Tooltip>
          );
        }

        return (
          <ComboboxItem
            key={item.value}
            value={item.value}
            selectedValue={value}
            onSelect={() => onSelect(item.value)}
            className="cursor-pointer"
          >
            <span className="truncate">{item.name}</span>
          </ComboboxItem>
        );
      })}
    </ComboboxList>
  );
}
