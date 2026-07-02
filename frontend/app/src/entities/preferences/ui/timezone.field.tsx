import { useMemo } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome omits plain "UTC" from the supported list (it exposes "Etc/UTC" instead), yet "UTC" is
// a valid, commonly-expected IANA zone. Ensure it is always selectable, without duplicating it on
// engines that already include it.
const TIMEZONES = RUNTIME_TIMEZONES.includes("UTC")
  ? RUNTIME_TIMEZONES
  : ["UTC", ...RUNTIME_TIMEZONES];

export interface TimezoneFieldProps {
  name: string;
  label: string;
  /** Extra classes for the field's own label (e.g. `sr-only` to hide it visually). */
  labelClassName?: string;
  /** Forwarded to the trigger so a hint can be announced by screen readers. */
  "aria-describedby"?: string;
  defaultValue?: FormAttributeValue;
  /** Placeholder shown in the trigger when nothing is selected. */
  placeholder?: string;
}

/** Searchable select over the IANA timezones supported by the runtime. */
export function TimezoneField({
  name,
  label,
  labelClassName,
  "aria-describedby": ariaDescribedBy,
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  placeholder = "Select timezone",
}: TimezoneFieldProps) {
  // Stable item identity across renders; the timezone list never changes at runtime.
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
