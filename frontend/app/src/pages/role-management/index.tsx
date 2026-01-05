import { gql } from "@apollo/client";
import { Outlet } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { GLOBAL_PERMISSION_OBJECT } from "@/shared/config/constants";

import { getObjectPermissionsQuery } from "@/entities/permission/queries/getObjectPermissions";
import { RoleManagementNavigation } from "@/entities/role-manager/ui";

function RoleManagement() {
  const { loading, error } = useQuery(gql(getObjectPermissionsQuery(GLOBAL_PERMISSION_OBJECT)));

  if (loading) {
    return <LoadingIndicator message="Checking permissions..." className="h-full" />;
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
