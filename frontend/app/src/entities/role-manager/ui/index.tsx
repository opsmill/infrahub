import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Tabs } from "@/shared/components/tabs-routes";

import { useGetCounts } from "@/entities/role-manager/ui/queries/get-counts.query";

export function RoleManagementNavigation() {
  const { isLoading, data, error } = useGetCounts();

  const tabs = [
    {
      to: constructPath("/role-management"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:user-outline"} />
          Accounts
        </div>
      ),
      count: data?.accounts,
      isLoading,
      error: !!error,
    },
    {
      to: constructPath("/role-management/groups"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:user-multiple-outline"} />
          Groups
        </div>
      ),
      count: data?.groups,
      isLoading,
      error: !!error,
    },
    {
      to: constructPath("/role-management/roles"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:user-circle-outline"} />
          Roles
        </div>
      ),
      count: data?.roles,
      isLoading,
      error: !!error,
    },
    {
      to: constructPath("/role-management/global-permissions"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:ticket-confirmation-outline"} />
          Global Permissions
        </div>
      ),
      count: data?.globalPermissions,
      isLoading,
      error: !!error,
    },
    {
      to: constructPath("/role-management/object-permissions"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:ticket-outline"} />
          Object Permissions
        </div>
      ),
      count: data?.objectPermissions,
      isLoading,
      error: !!error,
    },
  ];

  return <Tabs tabs={tabs} className="pr-2" />;
}
