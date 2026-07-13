import { Card, CardHeader } from "@infrahub/ui";
import { useMemo } from "react";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { ResolvedPreference } from "@/entities/preferences/domain/model/preference";
import {
  dateFormatLabel,
  formatDateFormatExample,
} from "@/entities/preferences/domain/rules/date-format";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

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

function sourceTooltip(resolved: ResolvedPreference, browserValue: string): string {
  switch (resolved.source) {
    case "USER":
      return "Your preference.";
    case "GLOBAL":
      return `From the organisation default: ${resolved.value}.`;
    case "DEFAULT":
      return `From your browser: ${browserValue}.`;
    default:
      // An unrecognised source shouldn't reach the client; surface it rather than silently
      // presenting it as a browser default (per IFC-2720).
      console.warn(`Unexpected preference source: ${String(resolved.source)}`);
      return `From your browser: ${browserValue}.`;
  }
}

export function UserPreferencesCard() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateMyUserPreferences();
  const now = useMemo(() => new Date(), []);

  if (effectiveQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  if (effectiveQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const preferences = effectiveQuery.data;

  const dateFormatResolved: ResolvedPreference = {
    source: preferences.dateFormat.source,
    value: preferences.dateFormat.value
      ? presetExample(preferences.dateFormat.value, now)
      : preferences.dateFormat.value,
  };
  const dateFormatSourceTooltip = sourceTooltip(dateFormatResolved, browserDateExample(now));
  const timezoneSourceTooltip = sourceTooltip(preferences.timezone, browserTimezone());

  // Show only the caller's OWN override; inherited values stay unset so the field shows its placeholder.
  const dateFormatOverride =
    preferences.dateFormat.source === "USER" ? preferences.dateFormat.value : null;
  const timezoneOverride =
    preferences.timezone.source === "USER" ? preferences.timezone.value : null;

  return (
    <Card className="w-full">
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
        onSubmit={async (values) => {
          try {
            await updatePreferences.mutateAsync(values);
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Preferences updated" />);
          } catch (error) {
            toast(
              <Alert
                type={ALERT_TYPES.ERROR}
                message={error instanceof Error ? error.message : "Failed to update preferences"}
              />
            );
            // Re-throw so the shared Form skips its post-submit reset() and stays dirty.
            throw error;
          }
        }}
        isSubmitDisabled={updatePreferences.isPending}
      />
    </Card>
  );
}
