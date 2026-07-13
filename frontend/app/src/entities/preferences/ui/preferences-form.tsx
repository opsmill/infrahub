import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import type React from "react";
import { useId, useMemo } from "react";
import { useFormState, useWatch } from "react-hook-form";

import { DetailRow } from "@/shared/components/display/detail-row";
import { ComboboxField } from "@/shared/components/form/fields/combobox.field";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";
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
  /** Placeholder for an unset field. Defaults to the user-scope wording; the org-defaults form
   * (which edits the raw defaults, not a child scope) passes its own copy. */
  emptyValueLabel?: string;
  onSubmit: (values: PreferenceValues) => Promise<void>;
  isSubmitDisabled?: boolean;
  children?: React.ReactNode;
}

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
  children,
}: PreferencesFormProps) {
  // The stored value is the preset key, not the human label.
  const items = useMemo(
    () => buildDateFormatPresets().map(({ key, label }) => ({ value: key, label })),
    []
  );
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
          dateFormat: (formData.date_format?.value as DateFormatKey | null) ?? null,
          timezone: (formData.timezone?.value as string | null) ?? null,
        });
      }}
    >
      {/* No horizontal padding on the divide-y container so dividers reach both card edges; each child pads itself. */}
      <div className="divide-y divide-gray-200">
        <DetailRow icon="mdi:calendar-text" label="Date format" labelId={dateFormatLabelId}>
          {/* Fixed w-64 + always-present flex-1 example slot (mirrored by the timezone spacer) keeps the (i) icons aligned across rows. */}
          <div className="flex items-center gap-2">
            <div className="w-64 shrink-0">
              <ComboboxField
                name="date_format"
                label="Date format"
                labelClassName="sr-only"
                items={items}
                placeholder={emptyValueLabel}
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
                placeholder={emptyValueLabel}
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
