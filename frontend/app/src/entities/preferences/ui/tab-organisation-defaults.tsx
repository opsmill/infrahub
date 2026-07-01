import { Card, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

export default function TabOrganisationDefaults() {
  // The gate stays on the effective query's `can_edit_global_preferences` flag,
  // while the form values come from the raw GLOBAL scope — so an admin who also
  // set personal overrides still prefills from the organisation's own defaults.
  const effectiveQuery = useEffectivePreferences();
  const globalQuery = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (effectiveQuery.error || globalQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching the organisation defaults" />;
  }

  if (effectiveQuery.isPending || globalQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (!effectiveQuery.data.canEditGlobalPreferences) {
    return <UnauthorizedScreen message="You don't have permission to edit organisation defaults" />;
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
              // Re-throw so the shared Form skips its post-submit reset(): a failed update must
              // keep the form dirty with the unsaved values, not look as though it saved.
              throw error;
            }
          }}
        />
      </Card>
    </main>
  );
}
