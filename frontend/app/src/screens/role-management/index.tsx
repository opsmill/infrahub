import { Tabs } from "@/components/tabs-routes";
import {
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_OBJECT,
  ACCOUNT_PERMISSION_OBJECT,
  ACCOUNT_ROLE_OBJECT,
} from "@/config/constants";
import { GET_ROLE_MANAGEMENT_COUNTS } from "@/graphql/queries/role-management/getCounts";
import useQuery from "@/hooks/useQuery";

import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Outlet } from "react-router-dom";

export function RoleManagementRoot() {
  const { loading, data, error } = useQuery(GET_ROLE_MANAGEMENT_COUNTS);

  const tabs = [
    {
      to: constructPath("/role-management"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:user-outline"} />
          Accounts
        </div>
      ),
      count: data && data[ACCOUNT_OBJECT]?.count,
      isLoading: loading,
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
      count: data && data[ACCOUNT_GROUP_OBJECT]?.count,
      isLoading: loading,
    },
    {
      to: constructPath("/role-management/roles"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:user-circle-outline"} />
          Roles
        </div>
      ),
      count: data && data[ACCOUNT_ROLE_OBJECT]?.count,
      isLoading: loading,
    },
    {
      to: constructPath("/role-management/permissions"),
      label: (
        <div className="flex items-center gap-2">
          <Icon icon={"mdi:ticket-account-outline"} />
          Permissions
        </div>
      ),
      count: data && data[ACCOUNT_PERMISSION_OBJECT]?.count,
      isLoading: loading,
    },
  ];

  return (
    <div>
      <Tabs tabs={tabs} className="pr-2" />

      <div className="p-4">
        <Outlet />
      </div>
    </div>
  );
}
