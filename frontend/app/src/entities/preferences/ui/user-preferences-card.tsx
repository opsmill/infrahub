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

/** Browser-locale date formatting: the fallback shown when source is "default". */
function browserDateExample(referenceDate: Date): string {
  return referenceDate.toLocaleString();
}

/** The browser's resolved IANA timezone, e.g. "Europe/Paris". */
function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function presetExample(value: string, referenceDate: Date) {
  // `value` is a semantic key; render its live example + human label, never the raw key,
  // e.g. "01/07/2026 14:30 (dd/MM/yyyy HH:mm)".
  return `${formatDateFormatExample(value, referenceDate)} (${dateFormatLabel(value)})`;
}

/** (i) tooltip text for a field's effective value, keyed off its resolved source. */
function sourceTooltip(resolved: ResolvedPreference, browserValue: string): string {
  switch (resolved.source) {
    case "USER":
      return "Your preference.";
    case "GLOBAL":
      return `From the organisation default: ${resolved.value}.`;
    default:
      return `From your browser: ${browserValue}.`;
  }
}

/** The user's personal date/time preferences card on the Profile tab. */
export function UserPreferencesCard() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateMyUserPreferences();
  // Single reference instant for the live date example, memoised so it does not churn.
  const now = useMemo(() => new Date(), []);

  if (effectiveQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  if (effectiveQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const preferences = effectiveQuery.data;

  // A raw semantic key is unhelpful in prose, so render a concrete date-format value as a
  // live preset example for the tooltip.
  const dateFormatResolved: ResolvedPreference = {
    source: preferences.dateFormat.source,
    value: preferences.dateFormat.value
      ? presetExample(preferences.dateFormat.value, now)
      : preferences.dateFormat.value,
  };
  const dateFormatSourceTooltip = sourceTooltip(dateFormatResolved, browserDateExample(now));
  const timezoneSourceTooltip = sourceTooltip(preferences.timezone, browserTimezone());

  // Show only the caller's OWN override: an inherited value (source !== "user") is left unset
  // so the field shows its "Automatic (inherited)" placeholder.
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
            // Re-throw so the shared Form skips its post-submit reset(), keeping the form dirty
            // with the unsaved values rather than looking as though it saved.
            throw error;
          }
        }}
        isSubmitDisabled={updatePreferences.isPending}
      />
    </Card>
  );
}
