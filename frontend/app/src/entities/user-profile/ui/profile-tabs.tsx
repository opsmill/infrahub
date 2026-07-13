import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";

export function ProfileTabs() {
  const { data: canManageGlobalPreferences = false } =
    useHasGlobalPermission(MANAGE_GLOBAL_PREFERENCES);

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab to="/profile">Profile</LinkTab>
        <LinkTab to="/profile/tokens">Tokens</LinkTab>
        <LinkTab to="/profile/password">Password</LinkTab>
        {canManageGlobalPreferences && (
          <LinkTab to="/profile/global-preferences">Global preferences</LinkTab>
        )}
      </Row>
    </nav>
  );
}
