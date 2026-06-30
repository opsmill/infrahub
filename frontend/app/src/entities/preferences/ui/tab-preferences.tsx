import { Button, Card, CardContent, CardHeader } from "@infrahub/ui";
import { useMemo } from "react";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import {
  DEFAULT_DATE_FORMAT,
  formatDateFormatExample,
} from "@/entities/preferences/domain/date-format-presets";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

function inheritedHint(globalValue: string | null | undefined, builtinFallback: string) {
  return `Inherited from organisation defaults: ${globalValue ?? builtinFallback}`;
}

function presetLabel(value: string | null | undefined, referenceDate: Date) {
  if (!value) return;
  return `${formatDateFormatExample(value, referenceDate)} (${value})`;
}

export default function TabPreferences() {
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

  return (
    <main className="p-2">
      <Card className="w-full max-w-md">
        <CardHeader>Preferences</CardHeader>
        <CardContent>
          <p className="mb-4 text-gray-600 text-sm">
            Personal overrides of the organisation defaults. Empty fields inherit the
            organisation-wide value.
          </p>

          <PreferencesForm
            values={{
              dateFormat: preferences.userDateFormat,
              timezone: preferences.userTimezone,
            }}
            dateFormatHint={
              preferences.userDateFormat
                ? undefined
                : inheritedHint(
                    presetLabel(preferences.globalDateFormat, now),
                    `${DEFAULT_DATE_FORMAT} (built-in default)`
                  )
            }
            timezoneHint={
              preferences.userTimezone
                ? undefined
                : inheritedHint(preferences.globalTimezone, "browser timezone")
            }
            onSubmit={async (values) => {
              try {
                await updatePreferences.mutateAsync(values);
                toast(<Alert type={ALERT_TYPES.SUCCESS} message="Preferences updated" />);
              } catch (error) {
                toast(
                  <Alert
                    type={ALERT_TYPES.ERROR}
                    message={
                      error instanceof Error ? error.message : "Failed to update preferences"
                    }
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
                    toast(
                      <Alert type={ALERT_TYPES.SUCCESS} message="Preferences reset to global" />
                    );
                  } catch (error) {
                    toast(
                      <Alert
                        type={ALERT_TYPES.ERROR}
                        message={
                          error instanceof Error ? error.message : "Failed to reset preferences"
                        }
                      />
                    );
                  }
                }}
              >
                Reset to global
              </Button>
            )}
          </PreferencesForm>
        </CardContent>
      </Card>
    </main>
  );
}
