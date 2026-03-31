import { Icon } from "@iconify-icon/react";
import { useMatch } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";
import {
  ACCOUNT_GENERIC_OBJECT,
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_ROLE_OBJECT,
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/shared/config/constants";

import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-tabs";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";

const tabs = [
  {
    to: constructPath("/role-management"),
    path: "/role-management",
    icon: "mdi:user-outline",
    label: "Accounts",
    kind: ACCOUNT_GENERIC_OBJECT,
  },
  {
    to: constructPath("/role-management/groups"),
    path: "/role-management/groups",
    icon: "mdi:user-multiple-outline",
    label: "Groups",
    kind: ACCOUNT_GROUP_OBJECT,
  },
  {
    to: constructPath("/role-management/roles"),
    path: "/role-management/roles",
    icon: "mdi:user-circle-outline",
    label: "Roles",
    kind: ACCOUNT_ROLE_OBJECT,
  },
  {
    to: constructPath("/role-management/global-permissions"),
    path: "/role-management/global-permissions",
    icon: "mdi:ticket-confirmation-outline",
    label: "Global Permissions",
    kind: GLOBAL_PERMISSION_OBJECT,
  },
  {
    to: constructPath("/role-management/object-permissions"),
    path: "/role-management/object-permissions",
    icon: "mdi:ticket-outline",
    label: "Object Permissions",
    kind: OBJECT_PERMISSION_OBJECT,
  },
] as const;

export function RoleManagementTabs() {
  return (
    <ScrollArea
      scrollX
      scrollY={false}
      scrollBarClassName="hidden"
      className="shrink-0 border-gray-200 border-b"
    >
      <Row className="items-end gap-4 px-4">
        {tabs.map((tab) => (
          <RoleManagementTab
            key={tab.path}
            to={tab.to}
            path={tab.path}
            icon={tab.icon}
            label={tab.label}
            kind={tab.kind}
          />
        ))}
      </Row>
    </ScrollArea>
  );
}

interface RoleManagementTabProps {
  to: string;
  path: string;
  icon: string;
  label: string;
  kind: string;
}

function RoleManagementTab({ to, path, icon, label, kind }: RoleManagementTabProps) {
  const match = useMatch(path);
  const { isPending, data: count } = useObjectsCount({ objectKind: kind });

  return (
    <ObjectDetailsTab isActive={!!match} to={to}>
      <Icon icon={icon} />
      {label}
      {isPending && <Spinner />}
      {!isPending && count !== undefined && (
        <Badge className="rounded-full font-medium text-gray-500">{count}</Badge>
      )}
    </ObjectDetailsTab>
  );
}
