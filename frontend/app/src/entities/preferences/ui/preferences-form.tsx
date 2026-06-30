import type React from "react";
import { useId, useMemo } from "react";
import { useFormState, useWatch } from "react-hook-form";

import { DetailRow } from "@/shared/components/display/detail-row";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import {
  buildDateFormatPresets,
  formatDateFormatExample,
} from "@/entities/preferences/domain/date-format-presets";
import type { PreferenceValues } from "@/entities/preferences/domain/types";
import { TimezoneField } from "@/entities/preferences/ui/timezone.field";

export interface PreferencesFormProps {
  values: PreferenceValues;
  dateFormatHint?: string;
  timezoneHint?: string;
  onSubmit: (values: PreferenceValues) => Promise<void>;
  isSubmitDisabled?: boolean;
  children?: React.ReactNode;
}

/** Save button disabled while the form is pristine, so an untouched form cannot be submitted. */
function SaveButton({ isDisabled }: { isDisabled?: boolean }) {
  const { isDirty } = useFormState();

  return <FormSubmit isDisabled={isDisabled || !isDirty}>Save</FormSubmit>;
}

function toFieldValue(value: string | null): FormAttributeValue {
  if (value === null) return { source: null, value: null };
  return { source: { type: "user" }, value };
}

/**
 * Live example of the currently-selected date format, sitting beside the control.
 * Watches the `date_format` field (whose value is a `{ source, value }` attribute)
 * and re-renders the example as the selection changes. `now` is memoised once per
 * mount so the example is stable across renders.
 */
function DateFormatExample({ id, now }: { id: string; now: Date }) {
  const fieldValue = useWatch({ name: "date_format" }) as FormAttributeValue | undefined;
  const selected = (fieldValue?.value as string | null | undefined) ?? null;

  if (!selected) return null;

  return (
    <p id={id} className="text-gray-500 text-xs">
      Example: {formatDateFormatExample(selected, now)}
    </p>
  );
}

/** Shared date-format + timezone form for the user and organisation tabs. */
export function PreferencesForm({
  values,
  dateFormatHint,
  timezoneHint,
  onSubmit,
  isSubmitDisabled,
  children,
}: PreferencesFormProps) {
  // Memoised so the item array identity is stable across renders. The presets are
  // `{ key, label }`; the ComboboxField takes `{ value, label }`, and the stored
  // value is the preset key.
  const items = useMemo(
    () => buildDateFormatPresets().map(({ key, label }) => ({ value: key, label })),
    []
  );
  // Single reference instant for the live example, memoised so it does not churn.
  const now = useMemo(() => new Date(), []);

  const dateFormatLabelId = useId();
  const timezoneLabelId = useId();
  const dateFormatExampleId = useId();
  const dateFormatHintId = useId();
  const timezoneHintId = useId();

  // The example and the inherited hint both describe the date-format control.
  const dateFormatDescribedBy =
    [dateFormatExampleId, dateFormatHint ? dateFormatHintId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <Form
      defaultValues={{
        date_format: toFieldValue(values.dateFormat),
        timezone: toFieldValue(values.timezone),
      }}
      onSubmit={async (formData) => {
        await onSubmit({
          dateFormat: (formData.date_format?.value as string | null) ?? null,
          timezone: (formData.timezone?.value as string | null) ?? null,
        });
      }}
    >
      {/* Separator between the rows, matching the object-details card layout. */}
      <div className="divide-y divide-gray-200">
        <DetailRow icon="mdi:calendar-text" label="Date format" labelId={dateFormatLabelId}>
          <ComboboxField
            name="date_format"
            label="Date format"
            labelClassName="sr-only"
            items={items}
            placeholder="Select date format"
            searchPlaceholder="Filter date formats..."
            emptyMessage="No date format found."
            aria-describedby={dateFormatDescribedBy}
          />
          <DateFormatExample id={dateFormatExampleId} now={now} />
          {dateFormatHint && (
            <p id={dateFormatHintId} className="text-gray-500 text-xs">
              {dateFormatHint}
            </p>
          )}
        </DetailRow>

        <DetailRow icon="mdi:earth" label="Timezone" labelId={timezoneLabelId}>
          <TimezoneField
            name="timezone"
            label="Timezone"
            labelClassName="sr-only"
            aria-describedby={timezoneHint ? timezoneHintId : undefined}
          />
          {timezoneHint && (
            <p id={timezoneHintId} className="text-gray-500 text-xs">
              {timezoneHint}
            </p>
          )}
        </DetailRow>
      </div>

      <div className="flex items-center justify-end gap-2">
        {children}
        <SaveButton isDisabled={isSubmitDisabled} />
      </div>
    </Form>
  );
}
