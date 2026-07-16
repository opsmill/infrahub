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

import type { Preference } from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  dateFormatLabel,
  formatDateFormatExample,
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

export function DateFormatField({ preference }: { preference: Preference }) {
  const now = new Date();
  const exampleId = React.useId();
  const items = buildDateFormatPresets().map(({ key, label }) => ({ value: key, label }));

  const fieldValue = useWatch({ name: "date_format" }) as FormAttributeValue | undefined;
  const selected = (fieldValue?.value as string | null | undefined) ?? null;

  const message = sourceMessage(preference, {
    formatGlobalValue: (value) =>
      `${formatDateFormatExample(value, now)} (${dateFormatLabel(value)})`,
    browserValue: now.toLocaleString(),
  });

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
                placeholder={EMPTY_VALUE_LABEL}
                emptyMessage="No date format found."
                aria-describedby={selected ? exampleId : undefined}
              />
            )}
          />
        </div>
        <div className="min-w-0 flex-1 truncate">
          {selected && (
            <p id={exampleId} className="truncate text-gray-500 text-xs">
              Example: {formatDateFormatExample(selected, now)}
            </p>
          )}
        </div>
        <SourceInfo message={message} />
      </Row>
    </DetailRow>
  );
}

export function TimezoneField({ preference }: { preference: Preference }) {
  const message = sourceMessage(preference, {
    formatGlobalValue: (value) => value,
    browserValue: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

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
                placeholder={EMPTY_VALUE_LABEL}
                emptyMessage="No timezone found."
                virtualized
              />
            )}
          />
        </div>
        <div className="flex-1" />
        <SourceInfo message={message} />
      </Row>
    </DetailRow>
  );
}
