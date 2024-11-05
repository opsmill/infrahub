import { GLOBAL_PERMISSION_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import UnauthorizedScreen from "@/screens/errors/unauthorized-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { getObjectPermissionsQuery } from "@/screens/permission/queries/getObjectPermissions";
import { RoleManagementNavigation } from "@/screens/role-management";
import { gql } from "@apollo/client";
import { Outlet } from "react-router-dom";

function RoleManagement() {
  const { loading, error } = useQuery(gql(getObjectPermissionsQuery(GLOBAL_PERMISSION_OBJECT)));

  if (loading) {
    return <LoadingScreen message="Loading permissions..." />;
  }

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching the permissions." />;
  }

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

export function Component() {
  return <RoleManagement />;
}
