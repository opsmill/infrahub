import { Outlet } from "react-router";

import Content from "@/shared/components/layout/content";

import { RoleManagementTabs } from "@/entities/role-manager/ui/role-management-tabs";

export function Component() {
  return (
    <Content.Card className="flex flex-col">
      <Content.CardTitle
        title="Users & Permissions"
        description="Accounts, groups, roles and permissions management"
        className="border-none p-4 pb-0"
      />

      <RoleManagementTabs />

      <Outlet />
    </Content.Card>
  );
}
