import { Card, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { RequireGlobalPermission } from "@/entities/permission/ui/require-global-permission";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

export default function TabOrganisationDefaults() {
  // The editor is mounted only once authorized, so it never handles the unauthorized state itself.
  return (
    <RequireGlobalPermission
      action={MANAGE_GLOBAL_PREFERENCES}
      loadingClassName="h-32"
      unauthorizedMessage="You don't have permission to edit organisation defaults"
    >
      <OrganisationDefaultsEditor />
    </RequireGlobalPermission>
  );
}

function OrganisationDefaultsEditor() {
  // Prefill from raw GLOBAL scope so an admin who also set personal overrides still sees the
  // org's own defaults, never their overrides.
  const globalQuery = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (globalQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching the organisation defaults" />;
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
              // Re-throw so the shared Form skips its post-submit reset(), keeping the form dirty
              // with the unsaved values rather than looking as though it saved.
              throw error;
            }
          }}
        />
      </Card>
    </main>
  );
}
