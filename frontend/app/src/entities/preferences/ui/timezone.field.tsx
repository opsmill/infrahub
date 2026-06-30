import { useMemo } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";

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
      placeholder="Select timezone"
      searchPlaceholder="Search timezone..."
      emptyMessage="No timezone found."
      labelClassName={labelClassName}
      aria-describedby={ariaDescribedBy}
      defaultValue={defaultValue}
    />
  );
}
