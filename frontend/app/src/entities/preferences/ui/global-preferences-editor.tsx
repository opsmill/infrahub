import { Card, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

export function GlobalPreferencesEditor() {
  const globalQuery = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (globalQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching the global preferences" />;
  }

  if (globalQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const global = globalQuery.data;

  return (
    <main className="p-2">
      <Card className="w-full max-w-3xl">
        <CardHeader>Global date and time</CardHeader>
        <p className="px-3 py-2 text-gray-600 text-sm">
          Defaults applied to every user unless they set a personal override.
        </p>

        <PreferencesForm
          values={{
            dateFormat: global.dateFormat,
            timezone: global.timezone,
          }}
          emptyValueLabel="Automatic (browser default)"
          onSubmit={(values) => {
            updatePreferences.mutate(values, {
              onSuccess: () => {
                toast(<Alert type={ALERT_TYPES.SUCCESS} message="Global preferences updated" />);
              },
              onError: (error) => {
                toast(
                  <Alert
                    type={ALERT_TYPES.ERROR}
                    message={
                      error instanceof Error ? error.message : "Failed to update global preferences"
                    }
                  />
                );
              },
            });
          }}
        />
      </Card>
    </main>
  );
}
