import { Card } from "@/components/ui/card";
import Content from "@/screens/layout/content";
import { RoleManagementRoot } from "@/screens/role-management";

function RoleManagement() {
  return (
    <Content className="p-2">
      <Card className="p-0 overflow-hidden">
        <Content.Title
          title={"Role Management"}
          description="Accounts, groups, roles and permissions management"
          className="border-b-0"
        />

        <RoleManagementRoot />
      </Card>
    </Content>
  );
}

export function Component() {
  return <RoleManagement />;
}
