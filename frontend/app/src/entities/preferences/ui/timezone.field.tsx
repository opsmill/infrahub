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

const TIMEZONES = Intl.supportedValuesOf("timeZone");

export interface TimezoneFieldProps {
  name: string;
  label: string;
  /** Extra classes for the field's own label (e.g. `sr-only` to hide it visually). */
  labelClassName?: string;
  /** Forwarded to the trigger so a hint can be announced by screen readers. */
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
}

/** Searchable select over the IANA timezones supported by the runtime. */
export function TimezoneField({
  name,
  label,
  labelClassName,
  "aria-describedby": ariaDescribedBy,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
}: TimezoneFieldProps) {
  const [open, setOpen] = useState(false);

  return (
    <FormField
      name={name}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const currentValue = (fieldData?.value as string | undefined) ?? null;

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField label={label} className={labelClassName} />

            <Combobox open={open} onOpenChange={setOpen}>
              <FormInput>
                <ComboboxTrigger aria-describedby={ariaDescribedBy}>
                  {currentValue ?? <span className="text-gray-400">Select timezone</span>}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList placeholder="Search timezone...">
                  <ComboboxEmpty>No timezone found.</ComboboxEmpty>
                  {TIMEZONES.map((timezone) => (
                    <ComboboxItem
                      key={timezone}
                      value={timezone}
                      selectedValue={currentValue}
                      onSelect={() => {
                        const newValue = timezone === currentValue ? null : timezone;
                        field.onChange(updateFormFieldValue(newValue, defaultValue));
                        setOpen(false);
                      }}
                    >
                      {timezone}
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
