import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { RequireGlobalPermission } from "@/entities/permission/ui/require-global-permission";
import { GlobalPreferencesEditor } from "@/entities/preferences/ui/global-preferences-editor";

function GlobalPreferencesPage() {
  return (
    <RequireGlobalPermission
      action={MANAGE_GLOBAL_PREFERENCES}
      loadingClassName="h-32"
      unauthorizedMessage="You don't have permission to edit global preferences"
    >
      <GlobalPreferencesEditor />
    </RequireGlobalPermission>
  );
}

export const Component = GlobalPreferencesPage;
