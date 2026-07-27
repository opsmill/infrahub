import { Autocomplete, Button, ListBox, ListBoxItem, Popover, PopoverTrigger } from "@infrahub/ui";
import { ChevronsUpDownIcon } from "lucide-react";
import { useState } from "react";
import type { Selection } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export interface ComboboxItem {
  value: string;
  label: string;
}

export interface ComboboxProps {
  value: string | null;
  onChange: (value: string | null) => void;
  items: ReadonlyArray<ComboboxItem>;
  /** Accessible name for the trigger and the option list. */
  label: string;
  placeholder?: string;
  emptyMessage?: string;
  "aria-describedby"?: string;
  /** Enable list virtualization for large option sets (e.g. timezones). */
  virtualized?: boolean;
  className?: string;
}

/**
 * Controlled single-select combobox with type-ahead search over its options.
 * Re-selecting the current value deselects it (`onChange(null)`), so callers get a
 * built-in "clear" without a separate control.
 */
export function Combobox({
  value,
  onChange,
  items,
  label,
  placeholder = "Select...",
  emptyMessage = "No match found.",
  "aria-describedby": ariaDescribedBy,
  virtualized = false,
  className,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);

  const currentLabel = items.find((item) => item.value === value)?.label ?? value;

  const handleSelectionChange = (keys: Selection) => {
    // Re-selecting the current value yields an empty set → null clears the selection.
    const [first] = keys === "all" ? [] : Array.from(keys);
    onChange(first === undefined ? null : String(first));
    setOpen(false);
  };

  return (
    <PopoverTrigger isOpen={open} onOpenChange={setOpen}>
      <Button
        variant="input"
        size="sm"
        aria-label={label}
        aria-describedby={ariaDescribedBy}
        className={classNames("w-full justify-between font-normal", className)}
      >
        <span className={classNames("truncate", currentLabel ? "" : "text-gray-400")}>
          {currentLabel ?? placeholder}
        </span>
        <ChevronsUpDownIcon className="ml-2 size-3.5 shrink-0 text-gray-400" />
      </Button>

      <Popover placement="bottom start" matchTriggerWidth>
        <Autocomplete>
          <ListBox
            aria-label={label}
            selectionMode="single"
            selectionIndicator="checkmark"
            disallowEmptySelection={false}
            selectedKeys={value ? [value] : []}
            onSelectionChange={handleSelectionChange}
            virtualized={virtualized}
            emptyMessage={emptyMessage}
            className="max-h-72"
          >
            {items.map((item) => (
              <ListBoxItem key={item.value} id={item.value} textValue={item.label}>
                {item.label}
              </ListBoxItem>
            ))}
          </ListBox>
        </Autocomplete>
      </Popover>
    </PopoverTrigger>
  );
}
