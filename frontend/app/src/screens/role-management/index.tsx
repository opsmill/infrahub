import { Tabs } from "@/components/tabs-routes";
import {
  ACCOUNT_GENERIC_OBJECT,
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_ROLE_OBJECT,
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/config/constants";
import { GET_ROLE_MANAGEMENT_COUNTS } from "@/graphql/queries/role-management/getCounts";
import useQuery from "@/hooks/useQuery";

import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";

export function RoleManagementNavigation() {
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
      count: data && data[ACCOUNT_GENERIC_OBJECT]?.count,
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
      count: data && data[ACCOUNT_ROLE_OBJECT]?.count,
      isLoading: loading,
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
      count: data && data[GLOBAL_PERMISSION_OBJECT]?.count,
      isLoading: loading,
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
      count: data && data[OBJECT_PERMISSION_OBJECT]?.count,
      isLoading: loading,
      error: !!error,
    },
  ];

  return <Tabs tabs={tabs} className="pr-2" />;
}
