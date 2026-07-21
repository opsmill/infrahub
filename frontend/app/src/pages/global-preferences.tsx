import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { RequireGlobalPermission } from "@/entities/permission/ui/require-global-permission";
import { GlobalPreferencesEditor } from "@/entities/preferences/ui/global-preferences-editor";

function GlobalPreferencesPage() {
  useTitle("Global preferences");

  return (
    <Content.Card>
      <Content.CardTitle title="Global preferences" />

      <RequireGlobalPermission
        action={MANAGE_GLOBAL_PREFERENCES}
        loadingClassName="h-32"
        unauthorizedMessage="You don't have permission to edit global preferences"
      >
        <GlobalPreferencesEditor />
      </RequireGlobalPermission>
    </Content.Card>
  );
}

export const Component = GlobalPreferencesPage;
