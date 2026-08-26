import { useFormState } from "react-hook-form";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";
import type { Preference, PreferenceValues } from "@/entities/preferences/domain/model/preference";
import { inheritedValue } from "@/entities/preferences/domain/rules/resolve-date-preferences";
import {
  DateFormatField,
  TimezoneField,
  toFieldValue,
} from "@/entities/preferences/ui/preference-fields";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpsertUserPreferences } from "@/entities/preferences/ui/queries/upsert-user-preferences.mutation";

/** Only the caller's OWN override pre-fills a field; inherited values stay unset (placeholder). */
function ownOverride<T extends string>(preference: Preference<T>): T | null {
  return preference.source === "USER" ? preference.value : null;
}

function SaveButton({ isPending }: { isPending?: boolean }) {
  const { isDirty } = useFormState();

  return (
    <FormSubmit isPending={isPending} isDisabled={!isDirty}>
      Save
    </FormSubmit>
  );
}

export function PreferencesForm() {
  const { isPending, error, data: preferences } = useGetEffectivePreferences();
  const updatePreferences = useUpsertUserPreferences();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

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
      <DateFormatField
        preference={preferences.dateFormat}
        fallbackTimezone={inheritedValue(preferences.timezone)}
      />
      <TimezoneField preference={preferences.timezone} />

      <Row className="justify-end p-2">
        <SaveButton isPending={updatePreferences.isPending} />
      </Row>
    </Form>
  );
}
