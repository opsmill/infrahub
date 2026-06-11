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

export interface TimezoneFieldProps {
  name: string;
  label: string;
  defaultValue?: FormAttributeValue;
}

/** Searchable select over the IANA timezones supported by the runtime. */
export function TimezoneField({
  name,
  label,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
}: TimezoneFieldProps) {
  const timezones = Intl.supportedValuesOf("timeZone");

  return (
    <FormField
      name={name}
      defaultValue={defaultValue}
      render={({ field }) => {
        const [open, setOpen] = useState(false);

        const fieldData: FormAttributeValue = field.value;
        const currentValue = (fieldData?.value as string | undefined) ?? null;

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField label={label} />

            <Combobox open={open} onOpenChange={setOpen}>
              <FormInput>
                <ComboboxTrigger>{currentValue}</ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList placeholder="Search timezone...">
                  <ComboboxEmpty>No timezone found.</ComboboxEmpty>
                  {timezones.map((timezone) => (
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
