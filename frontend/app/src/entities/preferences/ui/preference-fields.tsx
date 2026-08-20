import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import React from "react";
import { useWatch } from "react-hook-form";

import { Row } from "@/shared/components/container";
import { DetailRow } from "@/shared/components/display/detail-row";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Combobox, type ComboboxItem } from "@/shared/components/inputs/combobox";
import { FormField } from "@/shared/components/ui/form";
import { formatWithPreferences } from "@/shared/context/date-preferences-context";
import { supportedTimezone } from "@/shared/utils/date";

import type { Preference } from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  dateFormatLabel,
  dateFormatPattern,
} from "@/entities/preferences/domain/rules/date-format";

const EMPTY_VALUE_LABEL = "Automatic (inherited)";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome exposes "Etc/UTC" rather than plain "UTC", so ensure "UTC" is always selectable.
const TIMEZONE_ITEMS: Array<ComboboxItem> = (
  RUNTIME_TIMEZONES.includes("UTC") ? RUNTIME_TIMEZONES : ["UTC", ...RUNTIME_TIMEZONES]
).map((timezone) => ({ value: timezone, label: timezone }));

/** Map a plain value to the form's attribute shape; `null` resets to the "no override" default. */
export function toFieldValue(value: string | null): FormAttributeValue {
  if (value === null) return DEFAULT_FORM_FIELD_VALUE;
  return { source: { type: "user" }, value };
}

/** Explains where a field's effective value comes from, based on its resolved source. */
function sourceMessage(
  preference: Preference,
  {
    formatGlobalValue,
    browserValue,
  }: { formatGlobalValue: (value: string) => string; browserValue: string }
): string {
  switch (preference.source) {
    case "USER":
      return "Your preference.";
    case "GLOBAL":
      return preference.value
        ? `From the organisation default: ${formatGlobalValue(preference.value)}.`
        : `From your browser: ${browserValue}.`;
    default: // DEFAULT — browser locale fallback
      return `From your browser: ${browserValue}.`;
  }
}

/** Presentational (i) tooltip trigger — the message is resolved by the field that owns it. */
function SourceInfo({ message }: { message: string }) {
  return (
    <Tooltip message={<div className="max-w-60">{message}</div>}>
      <Button
        variant="ghost"
        shape="square"
        size="xs"
        aria-label="Where this value comes from"
        className="shrink-0 text-gray-400"
      >
        <Icon icon="mdi:information-outline" />
      </Button>
    </Tooltip>
  );
}

interface PreferenceFieldProps {
  /** Effective preference used to resolve the (i) source tooltip. Omit it (e.g. global editing) to hide the tooltip. */
  preference?: Preference;
  emptyValueLabel?: string;
}

interface DateFormatFieldProps extends PreferenceFieldProps {
  /** Zone the examples use while the form's timezone field is empty; omit for the browser's. */
  fallbackTimezone?: string | null;
}

export function DateFormatField({
  preference,
  emptyValueLabel = EMPTY_VALUE_LABEL,
  fallbackTimezone,
}: DateFormatFieldProps) {
  const now = new Date();
  const exampleId = React.useId();
  const items = buildDateFormatPresets().map(({ key, label }) => ({ value: key, label }));

  const fieldValue = useWatch({ name: "date_format" }) as FormAttributeValue | undefined;
  const selected = (fieldValue?.value as string | null | undefined) ?? null;

  // Previews what saving would produce, so it follows the form's own (possibly unsaved) zone.
  const timezoneValue = useWatch({ name: "timezone" }) as FormAttributeValue | undefined;
  const timezone = (timezoneValue?.value as string | null | undefined) ?? fallbackTimezone ?? null;
  const example = (key: string) =>
    formatWithPreferences(now, { pattern: dateFormatPattern(key), timezone });

  const message = preference
    ? sourceMessage(preference, {
        formatGlobalValue: (value) => `${example(value)} (${dateFormatLabel(value)})`,
        browserValue: formatWithPreferences(now, { pattern: null, timezone }),
      })
    : null;

  return (
    <DetailRow icon="mdi:calendar-text" label="Date format">
      <Row>
        <div className="w-64 shrink-0">
          <FormField
            name="date_format"
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
            render={({ field }) => (
              <Combobox
                value={(field.value?.value as string | null) ?? null}
                onChange={(newValue) => field.onChange(toFieldValue(newValue))}
                items={items}
                label="Date format"
                placeholder={emptyValueLabel}
                emptyMessage="No date format found."
                aria-describedby={selected ? exampleId : undefined}
              />
            )}
          />
        </div>
        <div className="min-w-0 flex-1 truncate">
          {selected && (
            <p id={exampleId} className="truncate text-gray-500 text-xs">
              Example: {example(selected)}
            </p>
          )}
        </div>
        {message && <SourceInfo message={message} />}
      </Row>
    </DetailRow>
  );
}

/** Resolves the (i) hint for a timezone, correcting the source claim when this browser can't apply it.
 * A resolved zone this runtime cannot render is silently displayed in the browser's own zone, so the
 * hint must report that fallback rather than claim the stored zone is in effect. */
function timezoneSourceMessage(preference: Preference, browserZone: string): string {
  if (preference.value && !supportedTimezone(preference.value)) {
    return `This browser can't display ${preference.value}; times are shown in ${browserZone}.`;
  }
  return sourceMessage(preference, {
    formatGlobalValue: (value) => value,
    browserValue: browserZone,
  });
}

export function TimezoneField({
  preference,
  emptyValueLabel = EMPTY_VALUE_LABEL,
}: PreferenceFieldProps) {
  const message = preference
    ? timezoneSourceMessage(preference, Intl.DateTimeFormat().resolvedOptions().timeZone)
    : null;

  return (
    <DetailRow icon="mdi:earth" label="Timezone">
      <Row>
        <div className="w-64 shrink-0">
          <FormField
            name="timezone"
            defaultValue={DEFAULT_FORM_FIELD_VALUE}
            render={({ field }) => (
              <Combobox
                value={(field.value?.value as string | null) ?? null}
                onChange={(newValue) => field.onChange(toFieldValue(newValue))}
                items={TIMEZONE_ITEMS}
                label="Timezone"
                placeholder={emptyValueLabel}
                emptyMessage="No timezone found."
                virtualized
              />
            )}
          />
        </div>
        <div className="flex-1" />
        {message && <SourceInfo message={message} />}
      </Row>
    </DetailRow>
  );
}
