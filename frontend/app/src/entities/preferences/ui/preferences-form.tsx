import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import type React from "react";
import { useId, useMemo } from "react";
import { useFormState, useWatch } from "react-hook-form";

import { DetailRow } from "@/shared/components/display/detail-row";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { PreferenceValues } from "@/entities/preferences/domain/model/preference";
import {
  buildDateFormatPresets,
  formatDateFormatExample,
} from "@/entities/preferences/domain/rules/date-format";
import { TimezoneField } from "@/entities/preferences/ui/timezone.field";

export interface PreferencesFormProps {
  values: PreferenceValues;
  /** Tooltip body explaining where the date-format field's effective value comes from. */
  dateFormatSourceTooltip?: React.ReactNode;
  /** Tooltip body explaining where the timezone field's effective value comes from. */
  timezoneSourceTooltip?: React.ReactNode;
  onSubmit: (values: PreferenceValues) => Promise<void>;
  isSubmitDisabled?: boolean;
  children?: React.ReactNode;
}

/** (i) tooltip explaining the SOURCE of a field's effective value. */
function SourceInfo({ message }: { message: React.ReactNode }) {
  if (!message) return null;
  return (
    <Tooltip message={<div className="max-w-60">{message}</div>}>
      {/* Must be a react-aria Button, not a plain <button>: TooltipTrigger only wires up
          hover/focus + aria on the former, and it needs to be a keyboard tab stop. */}
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

/** Disabled while the form is pristine, so an untouched form cannot be submitted. */
function SaveButton({ isDisabled }: { isDisabled?: boolean }) {
  const { isDirty } = useFormState();

  return <FormSubmit isDisabled={isDisabled || !isDirty}>Save</FormSubmit>;
}

function toFieldValue(value: string | null): FormAttributeValue {
  if (value === null) return { source: null, value: null };
  return { source: { type: "user" }, value };
}

/** Live example of the selected date format; renders nothing when no value is selected. */
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

/** Shared date-format + timezone form for the user and organisation tabs. */
export function PreferencesForm({
  values,
  dateFormatSourceTooltip,
  timezoneSourceTooltip,
  onSubmit,
  isSubmitDisabled,
  children,
}: PreferencesFormProps) {
  // ComboboxField takes `{ value, label }`; the stored value is the preset key.
  const items = useMemo(
    () => buildDateFormatPresets().map(({ key, label }) => ({ value: key, label })),
    []
  );
  // Single reference instant for the live example, memoised so it does not churn.
  const now = useMemo(() => new Date(), []);

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
          dateFormat: (formData.date_format?.value as string | null) ?? null,
          timezone: (formData.timezone?.value as string | null) ?? null,
        });
      }}
    >
      {/* Full-bleed separators: the `divide-y` container has no horizontal padding so dividers
          reach both card edges; each child supplies its own padding. */}
      <div className="divide-y divide-gray-200">
        <DetailRow icon="mdi:calendar-text" label="Date format" labelId={dateFormatLabelId}>
          {/* Both fields share the same fixed w-64 so they line up. The example is an
              always-present flex-1 slot (mirroring the timezone spacer) so the (i) icons on
              both rows stay pinned right and aligned whether or not an example shows. */}
          <div className="flex items-center gap-2">
            <div className="w-64 shrink-0">
              <ComboboxField
                name="date_format"
                label="Date format"
                labelClassName="sr-only"
                items={items}
                placeholder="Automatic (inherited)"
                searchPlaceholder="Filter date formats..."
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
              <TimezoneField
                name="timezone"
                label="Timezone"
                labelClassName="sr-only"
                placeholder="Automatic (inherited)"
              />
            </div>
            {/* Spacer mirroring the date-format example slot, so the (i) icons align. */}
            <div className="flex-1" />
            <SourceInfo message={timezoneSourceTooltip} />
          </div>
        </DetailRow>

        <div className="flex items-center justify-end gap-2 px-3 py-2">
          {children}
          <SaveButton isDisabled={isSubmitDisabled} />
        </div>
      </div>
    </Form>
  );
}
