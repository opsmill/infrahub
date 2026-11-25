import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form } from "@/shared/components/ui/form";

import type { DateFormatKey } from "@/entities/preferences/domain/model/date-format";
import {
  DateFormatField,
  SaveButton,
  saveWithToasts,
  TimezoneField,
  toFieldValue,
} from "@/entities/preferences/ui/preference-fields";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

const GLOBAL_EMPTY_VALUE_LABEL = "Automatic (browser default)";

export function GlobalPreferencesForm() {
  const { isPending, error, data: global } = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the global preferences" />;
  }

  return (
    <Form
      defaultValues={{
        date_format: toFieldValue(global.dateFormat),
        timezone: toFieldValue(global.timezone),
      }}
      onSubmit={(formData) =>
        saveWithToasts(
          () =>
            updatePreferences.mutateAsync({
              dateFormat: (formData.date_format?.value as DateFormatKey | null) ?? null,
              timezone: (formData.timezone?.value as string | null) ?? null,
            }),
          { success: "Global preferences updated", failure: "Failed to update global preferences" }
        )
      }
      className="space-y-0 divide-y"
    >
      <DateFormatField emptyValueLabel={GLOBAL_EMPTY_VALUE_LABEL} />
      <TimezoneField emptyValueLabel={GLOBAL_EMPTY_VALUE_LABEL} />

      <Row className="justify-end p-2">
        <SaveButton isPending={updatePreferences.isPending}>Save</SaveButton>
      </Row>
    </Form>
  );
}
