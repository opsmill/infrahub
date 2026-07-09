import { useState } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface ComboboxFieldItem {
  /** Stored value written back into the form's `{ source, value }` attribute. */
  value: string;
  label: string;
}

export interface ComboboxFieldProps {
  name: string;
  label: string;
  items: ReadonlyArray<ComboboxFieldItem>;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  labelClassName?: string;
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
}

/**
 * Searchable, presets-only select over a fixed `items` list; the type-to-filter is a convenience
 * over the list, never a free-text value. Re-selecting the current value clears it (see onSelect).
 */
export function ComboboxField({
  name,
  label,
  items,
  placeholder = "Select...",
  searchPlaceholder = "Filter...",
  emptyMessage = "No match found.",
  labelClassName,
  "aria-describedby": ariaDescribedBy,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
}: ComboboxFieldProps) {
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

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField label={label} className={labelClassName} />

            <Combobox open={open} onOpenChange={setOpen}>
              <FormInput>
                <ComboboxTrigger aria-describedby={ariaDescribedBy}>
                  {currentLabel ?? <span className="text-gray-400">{placeholder}</span>}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList placeholder={searchPlaceholder}>
                  <ComboboxEmpty>{emptyMessage}</ComboboxEmpty>
                  {items.map((item) => (
                    <ComboboxItem
                      key={item.value}
                      value={item.value}
                      selectedValue={currentValue}
                      onSelect={() => {
                        // Re-selecting the current value clears it (stores `null`).
                        const newValue = item.value === currentValue ? null : item.value;
                        field.onChange(updateFormFieldValue(newValue, defaultValue));
                        setOpen(false);
                      }}
                    >
                      {item.label}
                    </ComboboxItem>
                  ))}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            <FormMessage />
          </div>
        );
      }}
    />
  );
}
