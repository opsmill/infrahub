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

/**
 * Sentinel option value standing for "no personal override = inherit". It can never
 * collide with a real preset/timezone because it is not a valid date-fns pattern nor
 * an IANA timezone, and selecting it maps the field's stored value to `null`.
 */
export const AUTOMATIC_OPTION_VALUE = "__automatic__";

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
  /**
   * When provided, prepends an "inherit / no override" entry at the TOP of the list
   * with this label (e.g. "Automatic"). Its stored value is `null`: selecting it
   * clears the override, and a `null`/unset field DISPLAYS this label instead of the
   * placeholder. Mapping is fully contained here so every field that opts in behaves
   * identically.
   */
  automaticOption?: { label: string };
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
  automaticOption,
}: ComboboxFieldProps) {
  const [open, setOpen] = useState(false);

  // The "Automatic" entry (when opted in) sits at the TOP and carries the sentinel
  // value; it maps to/from a `null` stored value below. Real options follow.
  const displayedItems: ReadonlyArray<ComboboxFieldItem> = automaticOption
    ? [{ value: AUTOMATIC_OPTION_VALUE, label: automaticOption.label }, ...items]
    : items;

  return (
    <FormField
      name={name}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const storedValue = (fieldData?.value as string | undefined) ?? null;
        // With Automatic enabled a `null` stored value selects the sentinel, so the
        // trigger shows "Automatic" rather than the placeholder.
        const currentValue =
          automaticOption && storedValue === null ? AUTOMATIC_OPTION_VALUE : storedValue;
        const currentLabel =
          displayedItems.find((item) => item.value === currentValue)?.label ?? currentValue;

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
                {/* `activeValue` makes the currently-selected option open highlighted and
                    scrolled into view (cmdk otherwise activates the first item). It's the
                    same string used as each item's `value`, so the sentinel/mixed-case
                    values match exactly. */}
                <ComboboxList placeholder={searchPlaceholder} activeValue={currentValue}>
                  <ComboboxEmpty>{emptyMessage}</ComboboxEmpty>
                  {displayedItems.map((item) => (
                    <ComboboxItem
                      key={item.value}
                      value={item.value}
                      selectedValue={currentValue}
                      onSelect={() => {
                        // The sentinel stores `null` (clear the override). Re-selecting
                        // the current real value also clears it, as before.
                        const isAutomatic = item.value === AUTOMATIC_OPTION_VALUE;
                        const newValue =
                          isAutomatic || item.value === currentValue ? null : item.value;
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
