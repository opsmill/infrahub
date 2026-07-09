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
  /** Visible label shown in the trigger and the option list. */
  label: string;
}

export interface ComboboxFieldProps {
  name: string;
  label: string;
  /** Selectable options, presets-only — there is no custom/free-text entry. */
  items: ReadonlyArray<ComboboxFieldItem>;
  /** Placeholder shown in the trigger when nothing is selected. */
  placeholder?: string;
  /** Placeholder shown in the search/filter input. */
  searchPlaceholder?: string;
  /** Message shown when the type-to-filter matches no option. */
  emptyMessage?: string;
  /** Extra classes for the field's own label (e.g. `sr-only` to hide it visually). */
  labelClassName?: string;
  /** Forwarded to the trigger so a hint can be announced by screen readers. */
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
}

/**
 * Searchable, presets-only select over a fixed `items` list. Wraps the shared
 * {@link Combobox} primitives so every preferences dropdown (date format,
 * timezone) renders the exact same trigger and popover. Selection is constrained
 * to the provided items; the type-to-filter is a convenience over the list, never
 * a free-text value. Keeps the `{ source, value }` `FormAttributeValue` contract,
 * including reset/unset semantics (re-selecting the current value clears it).
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
                        // Re-selecting the currently-selected value clears it (stores
                        // `null`); selecting any other value sets that value.
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
