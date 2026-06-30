import { Card, CardContent, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

export default function TabOrganisationDefaults() {
  const effectiveQuery = useEffectivePreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (effectiveQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching the organisation defaults" />;
  }

  if (effectiveQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  const preferences = effectiveQuery.data;

  if (!preferences.canEditGlobalPreferences) {
    return <UnauthorizedScreen message="You don't have permission to edit organisation defaults" />;
  }

  return (
    <main className="p-2">
      <Card className="w-full max-w-md">
        <CardHeader>Organisation defaults</CardHeader>
        <CardContent>
          <p className="mb-4 text-gray-600 text-sm">
            Defaults applied to every user unless they set a personal override.
          </p>

          <PreferencesForm
            values={{
              dateFormat: preferences.globalDateFormat,
              timezone: preferences.globalTimezone,
            }}
            onSubmit={async (values) => {
              try {
                await updatePreferences.mutateAsync(values);
                toast(<Alert type={ALERT_TYPES.SUCCESS} message="Organisation defaults updated" />);
              } catch (error) {
                toast(
                  <Alert
                    type={ALERT_TYPES.ERROR}
                    message={
                      error instanceof Error
                        ? error.message
                        : "Failed to update organisation defaults"
                    }
                  />
                );
              }
            }}
          />
        </CardContent>
      </Card>
    </main>
  );
}
