import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import type React from "react";
import { useId } from "react";
import { useFormState, useWatch } from "react-hook-form";

import { DetailRow } from "@/shared/components/display/detail-row";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";
import type { PreferenceValues } from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  formatDateFormatExample,
} from "@/entities/preferences/domain/rules/date-format";
import { PreferenceSelect } from "@/entities/preferences/ui/preference-select";

const RUNTIME_TIMEZONES = Intl.supportedValuesOf("timeZone");
// V8/Chrome exposes "Etc/UTC" rather than plain "UTC", so ensure "UTC" is always selectable.
const TIMEZONE_ITEMS = (
  RUNTIME_TIMEZONES.includes("UTC") ? RUNTIME_TIMEZONES : ["UTC", ...RUNTIME_TIMEZONES]
).map((timezone) => ({ value: timezone, label: timezone }));

export interface PreferencesFormProps {
  values: PreferenceValues;
  dateFormatSourceTooltip?: React.ReactNode;
  timezoneSourceTooltip?: React.ReactNode;
  emptyValueLabel?: string;
  onSubmit: (values: PreferenceValues) => void;
  isSubmitDisabled?: boolean;
}

function SourceInfo({ message }: { message: React.ReactNode }) {
  if (!message) return null;
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

function SaveButton({ isDisabled }: { isDisabled?: boolean }) {
  const { isDirty } = useFormState();

  return <FormSubmit isDisabled={isDisabled || !isDirty}>Save</FormSubmit>;
}

function toFieldValue(value: string | null): FormAttributeValue {
  if (value === null) return { source: null, value: null };
  return { source: { type: "user" }, value };
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

export function PreferencesForm({
  values,
  dateFormatSourceTooltip,
  timezoneSourceTooltip,
  emptyValueLabel = "Automatic (inherited)",
  onSubmit,
  isSubmitDisabled,
}: PreferencesFormProps) {
  const items = buildDateFormatPresets().map(({ key, label }) => ({ value: key, label }));
  const now = new Date();

  const dateFormatLabelId = useId();
  const timezoneLabelId = useId();
  const dateFormatExampleId = useId();

  const dateFormatDescribedBy = dateFormatExampleId;

  return (
    <Form
      defaultValues={{
        date_format: toFieldValue(values.dateFormat),
        timezone: toFieldValue(values.timezone),
      }}
      onSubmit={async (formData) => {
        await onSubmit({
          dateFormat: (formData.date_format?.value as DateFormatKey | null) ?? null,
          timezone: (formData.timezone?.value as string | null) ?? null,
        });
      }}
    >
      <div className="divide-y divide-gray-200">
        <DetailRow icon="mdi:calendar-text" label="Date format" labelId={dateFormatLabelId}>
          <div className="flex items-center gap-2">
            <div className="w-64 shrink-0">
              <PreferenceSelect
                name="date_format"
                label="Date format"
                labelClassName="sr-only"
                items={items}
                placeholder={emptyValueLabel}
                emptyMessage="No date format found."
                aria-describedby={dateFormatDescribedBy}
              />
            </div>
            <div className="min-w-0 flex-1 truncate">
              <DateFormatExample id={dateFormatExampleId} now={now} />
            </div>
            <SourceInfo message={dateFormatSourceTooltip} />
          </div>
        </DetailRow>

        <DetailRow icon="mdi:earth" label="Timezone" labelId={timezoneLabelId}>
          <div className="flex items-center gap-2">
            <div className="w-64 shrink-0">
              <PreferenceSelect
                name="timezone"
                label="Timezone"
                labelClassName="sr-only"
                items={TIMEZONE_ITEMS}
                placeholder={emptyValueLabel}
                emptyMessage="No timezone found."
                virtualized
              />
            </div>
            <div className="flex-1" />
            <SourceInfo message={timezoneSourceTooltip} />
          </div>
        </DetailRow>

        <div className="flex items-center justify-end gap-2 px-3 py-2">
          <SaveButton isDisabled={isSubmitDisabled} />
        </div>
      </div>
    </Form>
  );
}
