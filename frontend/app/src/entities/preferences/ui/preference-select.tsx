import { Autocomplete, Button, ListBox, ListBoxItem, Popover, PopoverTrigger } from "@infrahub/ui";
import { ChevronsUpDownIcon } from "lucide-react";
import { useState } from "react";
import type { Selection } from "react-aria-components";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormLabel, FormMessage } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

export interface PreferenceSelectItem {
  value: string;
  label: string;
}

export interface PreferenceSelectProps {
  name: string;
  label: string;
  items: ReadonlyArray<PreferenceSelectItem>;
  placeholder?: string;
  emptyMessage?: string;
  labelClassName?: string;
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
  virtualized?: boolean;
}

export function PreferenceSelect({
  name,
  label,
  items,
  placeholder = "Select...",
  emptyMessage = "No match found.",
  labelClassName,
  "aria-describedby": ariaDescribedBy,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  virtualized = false,
}: PreferenceSelectProps) {
  const [open, setOpen] = useState(false);

  return (
    <FormField
      name={name}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const currentValue = (fieldData?.value as string | undefined) ?? null;
        const currentLabel =
          items.find((item) => item.value === currentValue)?.label ?? currentValue;

        const handleSelectionChange = (keys: Selection) => {
          // Re-selecting the current value deselects it (empty set) → null clears the override.
          const [first] = keys === "all" ? [] : Array.from(keys);
          const newValue = first === undefined ? null : String(first);
          field.onChange(updateFormFieldValue(newValue, defaultValue));
          setOpen(false);
        };

        return (
          <div className="flex flex-col gap-2">
            <FormLabel className={labelClassName}>{label}</FormLabel>

            <PopoverTrigger isOpen={open} onOpenChange={setOpen}>
              <FormInput>
                <Button
                  variant="outline"
                  size="sm"
                  aria-label={label}
                  aria-describedby={ariaDescribedBy}
                  className="w-full justify-between font-normal"
                >
                  <span className={classNames("truncate", currentLabel ? "" : "text-gray-400")}>
                    {currentLabel ?? placeholder}
                  </span>
                  <ChevronsUpDownIcon className="ml-2 size-3.5 shrink-0 text-gray-400" />
                </Button>
              </FormInput>

              <Popover placement="bottom start" matchTriggerWidth>
                <Autocomplete>
                  <ListBox
                    aria-label={label}
                    selectionMode="single"
                    selectionIndicator="checkmark"
                    disallowEmptySelection={false}
                    selectedKeys={currentValue ? [currentValue] : []}
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

            <FormMessage />
          </div>
        );
      }}
    />
  );
}
