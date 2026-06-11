import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { GLOBAL_PREFERENCE_OBJECT_KIND } from "@/entities/preferences/constants";

export function ProfileTabs() {
  // The frontend has no super-admin flag: update permission on
  // CoreGlobalPreference is the only gating mechanism for the admin tab.
  const { data: globalPreferencePermission } = useGetObjectPermissions(
    GLOBAL_PREFERENCE_OBJECT_KIND
  );
  const canManageGlobalPreferences = globalPreferencePermission?.update.isAllowed ?? false;

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab to="/profile">Profile</LinkTab>
        <LinkTab to="/profile/tokens">Tokens</LinkTab>
        <LinkTab to="/profile/password">Password</LinkTab>
        <LinkTab to="/profile/preferences">Preferences</LinkTab>
        {canManageGlobalPreferences && (
          <LinkTab to="/profile/organisation-defaults">Organisation defaults</LinkTab>
        )}
      </Row>
    </nav>
  );
}
