import { matchPath, useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbRoleManagement() {
  const { pathname } = useLocation();

  const isAccountsPage = matchPath({ path: "/role-management" }, pathname);
  const isGroupsPage = matchPath({ path: "/role-management/groups" }, pathname);
  const isRolesPage = matchPath({ path: "/role-management/roles" }, pathname);
  const isGlobalPermissionsPage = matchPath(
    { path: "/role-management/global-permissions" },
    pathname
  );
  const isObjectPermissionsPage = matchPath(
    { path: "/role-management/object-permissions" },
    pathname
  );

  return (
    <Breadcrumb data-testid="breadcrumb-role-management">
      <BreadcrumbItem href={constructPath("/role-management")}>Users & Permissions</BreadcrumbItem>
      {isAccountsPage && (
        <BreadcrumbItem href={constructPath("/role-management")}>Accounts</BreadcrumbItem>
      )}
      {isGroupsPage && (
        <BreadcrumbItem href={constructPath("/role-management/groups")}>Groups</BreadcrumbItem>
      )}
      {isRolesPage && (
        <BreadcrumbItem href={constructPath("/role-management/roles")}>Roles</BreadcrumbItem>
      )}
      {isGlobalPermissionsPage && (
        <BreadcrumbItem href={constructPath("/role-management/global-permissions")}>
          Global Permissions
        </BreadcrumbItem>
      )}
      {isObjectPermissionsPage && (
        <BreadcrumbItem href={constructPath("/role-management/object-permissions")}>
          Object Permissions
        </BreadcrumbItem>
      )}
    </Breadcrumb>
  );
}
