import Content from "@/screens/layout/content";
import { RoleManagementNavigation } from "@/screens/role-management";
import { Outlet } from "react-router-dom";

function RoleManagement() {
  return (
    <Content.Card>
      <Content.CardTitle
        title="Role Management"
        description="Accounts, groups, roles and permissions management"
        className="border-none"
      />

      <RoleManagementNavigation />

      <Outlet />
    </Content.Card>
  );
}

export function Component() {
  return <RoleManagement />;
}
