import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";

import { PreferenceSelect } from "@/entities/preferences/ui/preference-select";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome omits plain "UTC" (exposes "Etc/UTC" instead), so ensure it is always selectable
// without duplicating it on engines that already include it.
const TIMEZONES = RUNTIME_TIMEZONES.includes("UTC")
  ? RUNTIME_TIMEZONES
  : ["UTC", ...RUNTIME_TIMEZONES];

const TIMEZONE_ITEMS = TIMEZONES.map((timezone) => ({ value: timezone, label: timezone }));

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
  return (
    <PreferenceSelect
      name={name}
      label={label}
      items={TIMEZONE_ITEMS}
      placeholder={placeholder}
      emptyMessage="No timezone found."
      labelClassName={labelClassName}
      aria-describedby={ariaDescribedBy}
      defaultValue={defaultValue}
      virtualized
    />
  );
}
