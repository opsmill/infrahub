import { Outlet } from "react-router";

import Content from "@/shared/components/layout/content";

import { RoleManagementNavigation } from "@/entities/role-manager/ui";

export function Component() {
  return (
    <Content.Card>
      <Content.CardTitle
        title="Users & Permissions"
        description="Accounts, groups, roles and permissions management"
        className="border-none"
      />

      <RoleManagementNavigation />

      <Outlet />
    </Content.Card>
  );
}
