import { Button, Card, CardHeader } from "@infrahub/ui";
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

function inheritedHint(globalValue: string, source: string) {
  return `Inherited from organisation defaults: ${globalValue} (${source})`;
}

function presetExample(value: string, referenceDate: Date) {
  return `${formatDateFormatExample(value, referenceDate)} (${value})`;
}

/**
 * The user's personal date/time preferences, surfaced as a card on the Profile
 * tab below the object details. Empty fields inherit the organisation default,
 * and when that is also unset they fall back to the browser's own locale and
 * timezone (the hint shows a concrete browser-formatted example).
 */
export function UserPreferencesCard() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateMyUserPreferences();
  // Single reference instant for the inherited hint's live example, memoised so
  // it does not churn across renders.
  const now = useMemo(() => new Date(), []);

  if (effectiveQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  if (effectiveQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const preferences = effectiveQuery.data;
  // The user has a personal override when either of their own values is set.
  const hasUserOverride = preferences.userDateFormat !== null || preferences.userTimezone !== null;

  // When the user has no override the field inherits the organisation default;
  // when that is also unset the effective default is the browser's own value.
  const dateFormatHint = preferences.userDateFormat
    ? undefined
    : preferences.globalDateFormat
      ? inheritedHint(presetExample(preferences.globalDateFormat, now), "organisation default")
      : `Browser default: ${browserDateExample(now)}`;

  const timezoneHint = preferences.userTimezone
    ? undefined
    : preferences.globalTimezone
      ? inheritedHint(preferences.globalTimezone, "organisation default")
      : `Browser default: ${browserTimezone()}`;

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>Preferences</CardHeader>
      <p className="px-3 py-2 text-gray-600 text-sm">
        Personal overrides of the organisation defaults. Empty fields inherit the organisation-wide
        value, or the browser default when none is set.
      </p>

      <PreferencesForm
        values={{
          dateFormat: preferences.userDateFormat,
          timezone: preferences.userTimezone,
        }}
        dateFormatHint={dateFormatHint}
        timezoneHint={timezoneHint}
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
      >
        {hasUserOverride && (
          <Button
            variant="outline"
            isPending={updatePreferences.isPending}
            isDisabled={updatePreferences.isPending}
            onPress={async () => {
              try {
                // Reset to global = clear the caller's own override by
                // upserting explicit null for every field (no delete).
                await updatePreferences.mutateAsync({ dateFormat: null, timezone: null });
                toast(<Alert type={ALERT_TYPES.SUCCESS} message="Preferences reset to global" />);
              } catch (error) {
                toast(
                  <Alert
                    type={ALERT_TYPES.ERROR}
                    message={error instanceof Error ? error.message : "Failed to reset preferences"}
                  />
                );
              }
            }}
          >
            Reset to global
          </Button>
        )}
      </PreferencesForm>
    </Card>
  );
}
