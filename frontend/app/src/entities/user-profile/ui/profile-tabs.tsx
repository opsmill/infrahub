import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

import { useCanManageGlobalPreferences } from "@/entities/permission/ui/queries/use-can-manage-global-preferences";

export function ProfileTabs() {
  // StandardNode has no object permission; manage_global_preferences is the gating signal.
  const { data: canManageGlobalPreferences = false } = useCanManageGlobalPreferences();

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab to="/profile">Profile</LinkTab>
        <LinkTab to="/profile/tokens">Tokens</LinkTab>
        <LinkTab to="/profile/password">Password</LinkTab>
        {canManageGlobalPreferences && (
          <LinkTab to="/profile/organisation-defaults">Organisation defaults</LinkTab>
        )}
      </Row>
    </nav>
  );
}
