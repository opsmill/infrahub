import { Button, Card, CardContent, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import {
  DATE_FORMAT_PRESETS,
  DEFAULT_DATE_FORMAT,
} from "@/entities/preferences/domain/date-format-presets";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpdateMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

function inheritedHint(globalValue: string | null | undefined, builtinFallback: string) {
  return `Inherited from organisation defaults: ${globalValue ?? builtinFallback}`;
}

function presetLabel(value: string | null | undefined) {
  if (!value) return;
  return DATE_FORMAT_PRESETS.find((preset) => preset.key === value)?.label ?? value;
}

export default function TabPreferences() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateMyUserPreferences();

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
      <Card className="m-auto w-full max-w-md">
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
                    presetLabel(preferences.globalDateFormat),
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
