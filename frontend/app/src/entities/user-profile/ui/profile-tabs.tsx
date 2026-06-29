import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

import { useEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";

export function ProfileTabs() {
  // `GlobalPreference` is a StandardNode with no object permission; the
  // effective query's `can_edit_global_preferences` flag is the gating signal.
  const { data: preferences } = useEffectivePreferences();
  const canManageGlobalPreferences = preferences?.canEditGlobalPreferences ?? false;

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
