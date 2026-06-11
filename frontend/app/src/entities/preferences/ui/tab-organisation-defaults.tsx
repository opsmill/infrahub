import { Card, CardContent } from "@infrahub/ui";
import { toast } from "react-toastify";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { GLOBAL_PREFERENCE_OBJECT_KIND } from "@/entities/preferences/constants";
import { PreferencesForm } from "@/entities/preferences/ui/preferences-form";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

export default function TabOrganisationDefaults() {
  const permissionQuery = useGetObjectPermissions(GLOBAL_PREFERENCE_OBJECT_KIND);
  const globalQuery = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (permissionQuery.error || globalQuery.error) {
    return <ErrorScreen message="Something went wrong when fetching the organisation defaults" />;
  }

  if (permissionQuery.isPending || globalQuery.isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (!permissionQuery.data.update.isAllowed) {
    return <UnauthorizedScreen message={permissionQuery.data.update.message} />;
  }

  const globalPreference = globalQuery.data;

  if (!globalPreference) {
    return <ErrorScreen message="The organisation defaults could not be found" />;
  }

  return (
    <main className="p-2">
      <Card className="m-auto w-full max-w-md">
        <CardContent>
          <h3 className="mb-1 font-semibold leading-6">Organisation defaults</h3>
          <p className="mb-4 text-gray-600 text-sm">
            Defaults applied to every user unless they set a personal override.
          </p>

          <PreferencesForm
            values={{
              dateFormat: globalPreference.dateFormat,
              timezone: globalPreference.timezone,
            }}
            onSubmit={async (values) => {
              try {
                await updatePreferences.mutateAsync({ id: globalPreference.id, ...values });
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
