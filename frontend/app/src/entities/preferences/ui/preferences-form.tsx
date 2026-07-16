import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import React from "react";
import { useFormState, useWatch } from "react-hook-form";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Combobox, type ComboboxItem } from "@/shared/components/inputs/combobox";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";
import type { Preference, PreferenceValues } from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  dateFormatLabel,
  formatDateFormatExample,
} from "@/entities/preferences/domain/rules/date-format";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpsertUserPreferences } from "@/entities/preferences/ui/queries/upsert-user-preferences.mutation";

const EMPTY_VALUE_LABEL = "Automatic (inherited)";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome exposes "Etc/UTC" rather than plain "UTC", so ensure "UTC" is always selectable.
const TIMEZONE_ITEMS: Array<ComboboxItem> = (
  RUNTIME_TIMEZONES.includes("UTC") ? RUNTIME_TIMEZONES : ["UTC", ...RUNTIME_TIMEZONES]
).map((timezone) => ({ value: timezone, label: timezone }));

function toFieldValue(value: string | null): FormAttributeValue {
  if (value === null) return DEFAULT_FORM_FIELD_VALUE;
  return { source: { type: "user" }, value };
}

/** Only the caller's OWN override pre-fills a field; inherited values stay unset (placeholder). */
function ownOverride<T extends string>(preference: Preference<T>): T | null {
  return preference.source === "USER" ? preference.value : null;
}

function SaveButton({ isDisabled }: { isDisabled?: boolean }) {
  const { isDirty } = useFormState();

  return <FormSubmit isDisabled={isDisabled || !isDirty}>Save</FormSubmit>;
}

/**
 * (i) tooltip explaining where a field's effective value comes from. The message is derived
 * here, next to the field, from the effective preference — never precomputed by a parent.
 */
function SourceInfo({
  preference,
  browserValue,
  formatValue = (value) => value,
}: {
  preference: Preference;
  browserValue: string;
  formatValue?: (value: string) => string;
}) {
  const message = (() => {
    switch (preference.source) {
      case "USER":
        return "Your preference.";
      case "GLOBAL":
        return preference.value
          ? `From the organisation default: ${formatValue(preference.value)}.`
          : `From your browser: ${browserValue}.`;
      default: // DEFAULT — browser locale fallback
        return `From your browser: ${browserValue}.`;
    }
  })();

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

function DateFormatExample({ id, now }: { id: string; now: Date }) {
  const fieldValue = useWatch({ name: "date_format" }) as FormAttributeValue | undefined;
  const selected = (fieldValue?.value as string | null | undefined) ?? null;

  if (!selected) return null;

  return (
    <p id={id} className="truncate text-gray-500 text-xs">
      Example: {formatDateFormatExample(selected, now)}
    </p>
  );
}

function PreferenceComboboxField({
  name,
  label,
  items,
  emptyMessage,
  virtualized,
  ariaDescribedBy,
}: {
  name: string;
  label: string;
  items: ReadonlyArray<ComboboxItem>;
  emptyMessage: string;
  virtualized?: boolean;
  ariaDescribedBy?: string;
}) {
  return (
    <FormField
      name={name}
      defaultValue={DEFAULT_FORM_FIELD_VALUE}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        return (
          <Combobox
            value={(fieldData?.value as string | null) ?? null}
            onChange={(newValue) => field.onChange(toFieldValue(newValue))}
            items={items}
            label={label}
            placeholder={EMPTY_VALUE_LABEL}
            emptyMessage={emptyMessage}
            virtualized={virtualized}
            aria-describedby={ariaDescribedBy}
          />
        );
      }}
    />
  );
}

export function PreferencesForm() {
  const { isPending, error, data: preferences } = useGetEffectivePreferences();
  const updatePreferences = useUpsertUserPreferences();
  const dateFormatExampleId = React.useId();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  const now = new Date();
  const dateFormatItems = buildDateFormatPresets().map(({ key, label }) => ({ value: key, label }));

  return (
    <Form
      defaultValues={{
        date_format: toFieldValue(ownOverride(preferences.dateFormat)),
        timezone: toFieldValue(ownOverride(preferences.timezone)),
      }}
      onSubmit={(formData) => {
        const values: PreferenceValues = {
          dateFormat: (formData.date_format?.value as DateFormatKey | null) ?? null,
          timezone: (formData.timezone?.value as string | null) ?? null,
        };
        updatePreferences.mutate(values, {
          onSuccess: () => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Preferences updated" />);
          },
          onError: (mutationError) => {
            toast(
              <Alert
                type={ALERT_TYPES.ERROR}
                message={
                  mutationError instanceof Error
                    ? mutationError.message
                    : "Failed to update preferences"
                }
              />
            );
          },
        });
      }}
      className="space-y-0 divide-y divide-gray-200"
    >
      <DetailRow icon="mdi:calendar-text" label="Date format">
        <Row>
          <div className="w-64 shrink-0">
            <PreferenceComboboxField
              name="date_format"
              label="Date format"
              items={dateFormatItems}
              emptyMessage="No date format found."
              ariaDescribedBy={dateFormatExampleId}
            />
          </div>
          <div className="min-w-0 flex-1 truncate">
            <DateFormatExample id={dateFormatExampleId} now={now} />
          </div>
          <SourceInfo
            preference={preferences.dateFormat}
            browserValue={now.toLocaleString()}
            formatValue={(value) =>
              `${formatDateFormatExample(value, now)} (${dateFormatLabel(value)})`
            }
          />
        </Row>
      </DetailRow>

      <DetailRow icon="mdi:earth" label="Timezone">
        <Row>
          <div className="w-64 shrink-0">
            <PreferenceComboboxField
              name="timezone"
              label="Timezone"
              items={TIMEZONE_ITEMS}
              emptyMessage="No timezone found."
              virtualized
            />
          </div>
          <div className="flex-1" />
          <SourceInfo
            preference={preferences.timezone}
            browserValue={Intl.DateTimeFormat().resolvedOptions().timeZone}
          />
        </Row>
      </DetailRow>

      <Row className="justify-end p-2">
        <SaveButton isDisabled={updatePreferences.isPending} />
      </Row>
    </Form>
  );
}
