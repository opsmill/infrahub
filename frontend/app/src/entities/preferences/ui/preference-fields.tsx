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

import type {
  EffectivePreference,
  Preference,
} from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  dateFormatLabel,
  dateFormatPattern,
} from "@/entities/preferences/domain/rules/date-format";
import { inheritedValue } from "@/entities/preferences/domain/rules/resolve-date-preferences";

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

/** Explains where a field's PENDING value comes from — what saving the form as it stands would produce. */
function sourceMessage(
  own: string | null,
  inherited: Preference,
  {
    formatValue,
    browserValue,
  }: {
    /** Renders a stored value as a label. Required: each field must consciously choose one. */
    formatValue: (value: string) => string;
    /** The browser's own value, when the field has one worth naming. Omitted -> the clause is dropped. */
    browserValue?: string;
  }
): string {
  const fromBrowser = browserValue ? `From your browser: ${browserValue}.` : "From your browser.";

  if (own) {
    return inherited.source === "GLOBAL" && inherited.value
      ? `Your preference, overriding the organisation default: ${formatValue(inherited.value)}.`
      : "Your preference.";
  }
  return inherited.source === "GLOBAL" && inherited.value
    ? `From the organisation default: ${formatValue(inherited.value)}.`
    : fromBrowser;
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
  preference?: EffectivePreference;
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

  // Previews what saving would produce, so it follows the form's own (possibly unsaved) values.
  const timezoneValue = useWatch({ name: "timezone" }) as FormAttributeValue | undefined;
  const timezone = (timezoneValue?.value as string | null | undefined) ?? fallbackTimezone ?? null;
  const previewFormat = selected ?? (preference ? inheritedValue(preference) : null);
  // A null format is the browser's own rendering, which is exactly what saving no override produces.
  const example = formatWithPreferences(now, {
    pattern: previewFormat ? dateFormatPattern(previewFormat) : null,
    timezone,
  });

  // Labels only, and no browserValue: a rendered sample here would follow the live `timezone` above
  // rather than describing where the value comes from.
  const message = preference
    ? sourceMessage(selected, preference.inherited, { formatValue: dateFormatLabel })
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
                aria-describedby={exampleId}
              />
            )}
          />
        </div>
        <div className="min-w-0 flex-1 truncate">
          <p id={exampleId} className="truncate text-gray-500 text-xs">
            Example: {example}
          </p>
        </div>
        {message && <SourceInfo message={message} />}
      </Row>
    </DetailRow>
  );
}

/** Resolves the (i) hint for a timezone, correcting the source claim when this browser can't apply it.
 * A resolved zone this runtime cannot render is silently displayed in the browser's own zone, so the
 * hint must report that fallback rather than claim the pending zone is in effect. */
function timezoneSourceMessage(
  own: string | null,
  preference: EffectivePreference,
  browserZone: string
): string {
  const pending = own ?? inheritedValue(preference);
  if (pending && !supportedTimezone(pending)) {
    return `This browser can't display ${pending}; times are shown in ${browserZone}.`;
  }
  return sourceMessage(own, preference.inherited, {
    formatValue: (value) => value,
    browserValue: browserZone,
  });
}

export function TimezoneField({
  preference,
  emptyValueLabel = EMPTY_VALUE_LABEL,
}: PreferenceFieldProps) {
  const fieldValue = useWatch({ name: "timezone" }) as FormAttributeValue | undefined;
  const selected = (fieldValue?.value as string | null | undefined) ?? null;

  const message = preference
    ? timezoneSourceMessage(selected, preference, Intl.DateTimeFormat().resolvedOptions().timeZone)
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
