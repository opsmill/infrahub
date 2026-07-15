import { Card, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { Preference } from "@/entities/preferences/domain/model/preference";
import {
  dateFormatLabel,
  formatDateFormatExample,
} from "@/entities/preferences/domain/rules/date-format";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpsertUserPreferences } from "@/entities/preferences/ui/queries/upsert-user-preferences.mutation";

function browserDateExample(referenceDate: Date): string {
  return referenceDate.toLocaleString();
}

function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function presetExample(value: string, referenceDate: Date) {
  // `value` is a semantic key; render its live example + label, never the raw key.
  return `${formatDateFormatExample(value, referenceDate)} (${dateFormatLabel(value)})`;
}

function sourceTooltip(resolved: Preference, browserValue: string): string {
  switch (resolved.source) {
    case "USER":
      return "Your preference.";
    case "GLOBAL":
      return `From the organisation default: ${resolved.value}.`;
    default: // DEFAULT — browser locale fallback
      return `From your browser: ${browserValue}.`;
  }
}

export function UserPreferencesCard() {
  const { isPending, error, data: preferences } = useGetEffectivePreferences();
  const updatePreferences = useUpsertUserPreferences();
  const now = new Date();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  const dateFormatPreference: Preference = {
    source: preferences.dateFormat.source,
    value: preferences.dateFormat.value
      ? presetExample(preferences.dateFormat.value, now)
      : preferences.dateFormat.value,
  };
  const dateFormatSourceTooltip = sourceTooltip(dateFormatPreference, browserDateExample(now));
  const timezoneSourceTooltip = sourceTooltip(preferences.timezone, browserTimezone());

  // Show only the caller's OWN override; inherited values stay unset so the field shows its placeholder.
  const dateFormatOverride =
    preferences.dateFormat.source === "USER" ? preferences.dateFormat.value : null;
  const timezoneOverride =
    preferences.timezone.source === "USER" ? preferences.timezone.value : null;

  return (
    <Card>
      <CardHeader>Preferences</CardHeader>
      <p className="px-3 py-2 text-gray-600 text-sm">
        Personal overrides of the organisation defaults. A field with no personal override inherits
        the organisation-wide value, or the browser default when none is set. Selecting a value
        overrides it; re-selecting the currently-selected value clears the override.
      </p>

      <PreferencesForm
        values={{
          dateFormat: dateFormatOverride,
          timezone: timezoneOverride,
        }}
        dateFormatSourceTooltip={dateFormatSourceTooltip}
        timezoneSourceTooltip={timezoneSourceTooltip}
        onSubmit={(values) => {
          updatePreferences.mutate(values, {
            onSuccess: () => {
              toast(<Alert type={ALERT_TYPES.SUCCESS} message="Preferences updated" />);
            },
            onError: (error) => {
              toast(
                <Alert
                  type={ALERT_TYPES.ERROR}
                  message={error instanceof Error ? error.message : "Failed to update preferences"}
                />
              );
            },
          });
        }}
        isSubmitDisabled={updatePreferences.isPending}
      />
    </Card>
  );
}
