import { Card, CardHeader } from "@infrahub/ui";
import { useMemo } from "react";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import {
  dateFormatLabel,
  formatDateFormatExample,
} from "@/entities/preferences/domain/date-format-presets";
import type { ResolvedPreference } from "@/entities/preferences/domain/types";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

/**
 * The browser's own locale formatting of a date — used as the effective default
 * for the date-format hint when neither the user nor the organisation has set a
 * value. Mirrors the app-wide rendering fallback (browser locale) rather than a
 * fixed pattern.
 */
function browserDateExample(referenceDate: Date): string {
  return referenceDate.toLocaleString();
}

/** The browser's resolved IANA timezone, e.g. "Europe/Paris". */
function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function presetExample(value: string, referenceDate: Date) {
  // `value` is a semantic key (e.g. "EU_DATETIME"); show its live example plus the human label,
  // never the raw key — e.g. "01/07/2026 14:30 (dd/MM/yyyy HH:mm)".
  return `${formatDateFormatExample(value, referenceDate)} (${dateFormatLabel(value)})`;
}

/**
 * Builds the (i) tooltip text describing the SOURCE of a field's effective value.
 * The source is read directly from the resolved preference (no comparison logic):
 *   - "user"    → "Your preference."
 *   - "global"  → "From the organisation default: <resolved value>." (when the source
 *                 is global the resolved value IS the org default).
 *   - "default" → "From your browser: <browser value>." (computed client-side).
 */
function sourceTooltip(resolved: ResolvedPreference, browserValue: string): string {
  switch (resolved.source) {
    case "user":
      return "Your preference.";
    case "global":
      return `From the organisation default: ${resolved.value}.`;
    default:
      return `From your browser: ${browserValue}.`;
  }
}

/**
 * The user's personal date/time preferences, surfaced as a card on the Profile
 * tab below the object details. A field with no personal override inherits the
 * organisation default, or the browser's own locale/timezone when that is also
 * unset. The (i) tooltip beside each field spells out where the current effective
 * value comes from.
 */
export function UserPreferencesCard() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateMyUserPreferences();
  // Single reference instant for the source tooltip's live date example, memoised so
  // it does not churn across renders.
  const now = useMemo(() => new Date(), []);

  if (effectiveQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  if (effectiveQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const preferences = effectiveQuery.data;

  // The (i) tooltip reads the resolved source directly. For the date-format field a
  // raw semantic key is unhelpful in prose, so when it resolves to a concrete value we
  // render it as a live preset example (e.g. "30/06/2026 14:30 (dd/MM/yyyy HH:mm)").
  const dateFormatResolved: ResolvedPreference = {
    source: preferences.dateFormat.source,
    value: preferences.dateFormat.value
      ? presetExample(preferences.dateFormat.value, now)
      : preferences.dateFormat.value,
  };
  const dateFormatSourceTooltip = sourceTooltip(dateFormatResolved, browserDateExample(now));
  const timezoneSourceTooltip = sourceTooltip(preferences.timezone, browserTimezone());

  // The form shows the caller's OWN override per field: when the value is inherited
  // (source !== "user") there is no override, so the field is left unset and shows
  // its "Automatic (inherited)" placeholder.
  const dateFormatOverride =
    preferences.dateFormat.source === "user" ? preferences.dateFormat.value : null;
  const timezoneOverride =
    preferences.timezone.source === "user" ? preferences.timezone.value : null;

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
            // Re-throw so the shared Form does not run its post-submit reset(): a failed update
            // must keep the form dirty with the unsaved values, not look as though it saved.
            throw error;
          }
        }}
        isSubmitDisabled={updatePreferences.isPending}
      />
    </Card>
  );
}
