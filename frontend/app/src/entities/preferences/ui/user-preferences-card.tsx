import { Card, CardHeader } from "@infrahub/ui";
import { useMemo } from "react";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { formatDateFormatExample } from "@/entities/preferences/domain/date-format-presets";
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
  return `${formatDateFormatExample(value, referenceDate)} (${value})`;
}

/**
 * Builds the (i) tooltip text describing the SOURCE of a field's current effective
 * value. Selecting "Automatic" (no override) is the common case here, so the text
 * resolves to where the value actually comes from:
 *   - user override set  → "Your preference."
 *   - no override + global set → "From the organisation default: <value>."
 *   - no override + no global  → "From your browser: <value>."
 */
function sourceTooltip(
  userValue: string | null,
  globalValue: string | null,
  browserValue: string
): string {
  if (userValue !== null) return "Your preference.";
  if (globalValue !== null) return `From the organisation default: ${globalValue}.`;
  return `From your browser: ${browserValue}.`;
}

/**
 * The user's personal date/time preferences, surfaced as a card on the Profile
 * tab below the object details. Each field offers an "Automatic" option meaning
 * "no personal override": the value then inherits the organisation default, or the
 * browser's own locale/timezone when that is also unset. The (i) tooltip beside
 * each field spells out where the current effective value comes from.
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

  // The (i) tooltip resolves to the field's effective source: the user's own
  // preference, the inherited organisation default, or the browser fallback.
  const dateFormatSourceTooltip = sourceTooltip(
    preferences.userDateFormat,
    preferences.globalDateFormat ? presetExample(preferences.globalDateFormat, now) : null,
    browserDateExample(now)
  );
  const timezoneSourceTooltip = sourceTooltip(
    preferences.userTimezone,
    preferences.globalTimezone,
    browserTimezone()
  );

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>Preferences</CardHeader>
      <p className="px-3 py-2 text-gray-600 text-sm">
        Personal overrides of the organisation defaults. Choose "Automatic" to inherit the
        organisation-wide value, or the browser default when none is set.
      </p>

      <PreferencesForm
        values={{
          dateFormat: preferences.userDateFormat,
          timezone: preferences.userTimezone,
        }}
        includeAutomatic
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
          }
        }}
        isSubmitDisabled={updatePreferences.isPending}
      />
    </Card>
  );
}
