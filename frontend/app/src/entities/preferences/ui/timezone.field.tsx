import { useMemo } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome omits plain "UTC" (exposes "Etc/UTC" instead), so ensure it is always selectable
// without duplicating it on engines that already include it.
const TIMEZONES = RUNTIME_TIMEZONES.includes("UTC")
  ? RUNTIME_TIMEZONES
  : ["UTC", ...RUNTIME_TIMEZONES];

export interface TimezoneFieldProps {
  name: string;
  label: string;
  labelClassName?: string;
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
  placeholder?: string;
}

export function TimezoneField({
  name,
  label,
  labelClassName,
  "aria-describedby": ariaDescribedBy,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  placeholder = "Select timezone",
}: TimezoneFieldProps) {
  const items = useMemo(
    () => TIMEZONES.map((timezone) => ({ value: timezone, label: timezone })),
    []
  );

  return (
    <ComboboxField
      name={name}
      label={label}
      items={items}
      placeholder={placeholder}
      searchPlaceholder="Search timezone..."
      emptyMessage="No timezone found."
      labelClassName={labelClassName}
      aria-describedby={ariaDescribedBy}
      defaultValue={defaultValue}
    />
  );
}
