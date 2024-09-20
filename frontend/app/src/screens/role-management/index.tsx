import { Tabs } from "@/components/tabs";
import { Accounts } from "./accounts";
import { Groups } from "./groups";
import { Roles } from "./roles";
import { Permissions } from "./permissions";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "@/config/qsp";
import { ReactNode } from "react";
import {
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_OBJECT,
  ACCOUNT_PERMISSION_OBJECT,
  ACCOUNT_ROLE_OBJECT,
} from "@/config/constants";

const content: Record<string, ReactNode> = {
  [ACCOUNT_OBJECT]: <Accounts />,
  [ACCOUNT_GROUP_OBJECT]: <Groups />,
  [ACCOUNT_ROLE_OBJECT]: <Roles />,
  [ACCOUNT_PERMISSION_OBJECT]: <Permissions />,
};

export function RoleManagementRoot() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  const tabs = [
    {
      name: ACCOUNT_OBJECT,
      label: "Accounts",
    },
    {
      name: ACCOUNT_GROUP_OBJECT,
      label: "Groups",
    },
    {
      name: ACCOUNT_ROLE_OBJECT,
      label: "Roles",
    },
    {
      name: ACCOUNT_PERMISSION_OBJECT,
      label: "Permissions",
    },
  ];

  return (
    <div>
      <Tabs tabs={tabs} className="pr-2" />

      <div className="p-4">{qspTab ? content[qspTab] : content[ACCOUNT_OBJECT]}</div>
    </div>
  );
}
