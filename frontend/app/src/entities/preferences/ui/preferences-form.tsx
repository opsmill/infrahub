import type React from "react";
import { useMemo } from "react";
import { useFormState } from "react-hook-form";

import { SelectField } from "@/shared/components/form/fields/select.field";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { buildDateFormatPresets } from "@/entities/preferences/domain/date-format-presets";
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

/** Shared date-format + timezone form for the user and organisation tabs. */
export function PreferencesForm({
  values,
  dateFormatHint,
  timezoneHint,
  onSubmit,
  isSubmitDisabled,
  children,
}: PreferencesFormProps) {
  // Memoised so the item array identity is stable across renders, which the
  // React Aria Select relies on; built once from the current date.
  const items = useMemo(() => buildDateFormatPresets(), []);

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
      <div className="space-y-1">
        <SelectField name="date_format" label="Date format" items={items} />
        {dateFormatHint && <p className="text-gray-600 text-sm">{dateFormatHint}</p>}
      </div>

      <div className="space-y-1">
        <TimezoneField name="timezone" label="Timezone" />
        {timezoneHint && <p className="text-gray-600 text-sm">{timezoneHint}</p>}
      </div>

      <div className="flex items-center justify-end gap-2">
        {children}
        <SaveButton isDisabled={isSubmitDisabled} />
      </div>
    </Form>
  );
}
