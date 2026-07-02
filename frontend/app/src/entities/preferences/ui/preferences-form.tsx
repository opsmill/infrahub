import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
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
  /** Tooltip body explaining where the date-format field's effective value comes from. */
  dateFormatSourceTooltip?: React.ReactNode;
  /** Tooltip body explaining where the timezone field's effective value comes from. */
  timezoneSourceTooltip?: React.ReactNode;
  onSubmit: (values: PreferenceValues) => Promise<void>;
  isSubmitDisabled?: boolean;
  children?: React.ReactNode;
}

/**
 * Small (i) trigger sitting to the right of a field, explaining the SOURCE of the
 * field's current effective value via a Tooltip. The trigger is a real `<button>`
 * (a natural tab stop) with an accessible name, so the explanation is reachable by
 * keyboard, not hover-only.
 */
function SourceInfo({ message }: { message: React.ReactNode }) {
  if (!message) return null;
  return (
    <Tooltip message={<div className="max-w-60">{message}</div>}>
      {/*
        A real react-aria Button so the trigger is a keyboard tab stop with an
        accessible name and the Tooltip wires up hover/focus + aria correctly
        (a plain <button> is not picked up by react-aria's TooltipTrigger).
      */}
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
 * Live example of the currently-selected date format, sitting INLINE to the right
 * of the control. Watches the `date_format` field (whose value is a
 * `{ source, value }` attribute) and re-renders the example as the selection
 * changes. `now` is memoised once per mount so the example is stable across renders.
 *
 * The example truncates so the longest preset never overflows the row or forces the
 * combobox to reflow; it renders nothing when no value is selected (the always-present
 * flex-1 wrapper in the row keeps the (i) icon pinned right regardless).
 */
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

  // The live example describes the date-format control. The source explanation now
  // lives in an adjacent (i) tooltip with its own focusable trigger, so it is no
  // longer wired in via aria-describedby.
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
      {/*
        Full-bleed separators, matching the object-details card layout: the
        `divide-y` container carries NO horizontal padding so the divider lines
        reach both card edges, while each child (the rows via DetailRow's `px-3`
        and the action row below) carries its own horizontal padding. The action
        row is the last child of the same container, so it sits under a
        full-width line too.
      */}
      <div className="divide-y divide-gray-200">
        <DetailRow icon="mdi:calendar-text" label="Date format" labelId={dateFormatLabelId}>
          {/*
            Control + live example + (i) source tooltip on a single row:
            [combobox (fixed w-64, shrink-0)] [example slot (flex-1, truncates)] [(i)].
            Both fields' inputs use the SAME fixed width (so they line up and one is
            not squeezed smaller than the other). The example slot is an always-present
            flex-1 wrapper — exactly like the timezone row's spacer — so the (i) icon is
            pinned to the far right whether or not an example is shown, and the two rows'
            (i) icons stay aligned.
          */}
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
            {/* Spacer so the (i) icon sits at the far right, aligned with the date-format
                row's (i) (which the flex-1 example pushes there). */}
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
