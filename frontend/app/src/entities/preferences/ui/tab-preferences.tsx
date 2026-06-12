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
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useMyUserPreferences } from "@/entities/preferences/ui/queries/get-my-user-preferences.query";
import { useResetMyUserPreferences } from "@/entities/preferences/ui/queries/reset-my-user-preferences.mutation";
import { useUpsertMyUserPreferences } from "@/entities/preferences/ui/queries/upsert-my-user-preferences.mutation";

function inheritedHint(globalValue: string | null | undefined, builtinFallback: string) {
  return `Inherited from organisation defaults: ${globalValue ?? builtinFallback}`;
}

function presetLabel(value: string | null | undefined) {
  if (!value) return;
  return DATE_FORMAT_PRESETS.find((preset) => preset.key === value)?.label ?? value;
}

export default function TabPreferences() {
  const globalQuery = useGlobalPreferences();
  const userQuery = useMyUserPreferences();
  const upsertPreferences = useUpsertMyUserPreferences();
  const resetPreferences = useResetMyUserPreferences();

  if (userQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching your preferences" />;
  }

  if (globalQuery.isPending || userQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  // Global preferences only power the inheritance hints: if that read fails,
  // treat the global values as unset instead of blocking the user's own form.
  const globalPreference = globalQuery.error ? undefined : globalQuery.data;
  const userPreference = userQuery.data;

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
              dateFormat: userPreference?.dateFormat ?? null,
              timezone: userPreference?.timezone ?? null,
            }}
            dateFormatHint={
              userPreference?.dateFormat
                ? undefined
                : inheritedHint(
                    presetLabel(globalPreference?.dateFormat),
                    `${DEFAULT_DATE_FORMAT} (built-in default)`
                  )
            }
            timezoneHint={
              userPreference?.timezone
                ? undefined
                : inheritedHint(globalPreference?.timezone, "browser timezone")
            }
            onSubmit={async (values) => {
              try {
                await upsertPreferences.mutateAsync(values);
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
            isSubmitDisabled={resetPreferences.isPending}
          >
            {userPreference && (
              <Button
                variant="outline"
                isPending={resetPreferences.isPending}
                isDisabled={upsertPreferences.isPending}
                onPress={async () => {
                  try {
                    await resetPreferences.mutateAsync({ id: userPreference.id });
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
