import { Icon } from "@iconify-icon/react";
import { ScrollArea, Spinner } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useConstructPath } from "@/entities/navigation/ui/hooks/use-construct-path";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/entities/permission/domain/model/permission";
import {
  ACCOUNT_GENERIC_OBJECT,
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_ROLE_OBJECT,
} from "@/entities/role-manager/domain/model/account";

const TABS = [
  {
    path: "/role-management",
    icon: "mdi:user-outline",
    label: "Accounts",
    kind: ACCOUNT_GENERIC_OBJECT,
  },
  {
    path: "/role-management/groups",
    icon: "mdi:user-multiple-outline",
    label: "Groups",
    kind: ACCOUNT_GROUP_OBJECT,
  },
  {
    path: "/role-management/roles",
    icon: "mdi:user-circle-outline",
    label: "Roles",
    kind: ACCOUNT_ROLE_OBJECT,
  },
  {
    path: "/role-management/global-permissions",
    icon: "mdi:ticket-confirmation-outline",
    label: "Global Permissions",
    kind: GLOBAL_PERMISSION_OBJECT,
  },
  {
    path: "/role-management/object-permissions",
    icon: "mdi:ticket-outline",
    label: "Object Permissions",
    kind: OBJECT_PERMISSION_OBJECT,
  },
] as const;

export function RoleManagementTabs() {
  const constructPath = useConstructPath();

  return (
    <ScrollArea
      scrollX
      scrollY={false}
      scrollBarClassName="hidden"
      className="shrink-0 border-gray-200 border-b"
    >
      <nav aria-label="Tabs">
        <Row className="items-end gap-4 px-4">
          {TABS.map((tab) => (
            <RoleManagementTab
              key={tab.path}
              to={constructPath(tab.path)}
              icon={tab.icon}
              label={tab.label}
              kind={tab.kind}
            />
          ))}
        </Row>
      </nav>
    </ScrollArea>
  );
}

interface RoleManagementTabProps {
  to: string;
  icon: string;
  label: string;
  kind: string;
}

function RoleManagementTab({ to, icon, label, kind }: RoleManagementTabProps) {
  const { isPending, data: count } = useObjectsCount({ objectKind: kind });

  return (
    <LinkTab to={to}>
      <Icon icon={icon} />
      {label}
      {isPending && <Spinner />}
      {!isPending && count !== undefined && (
        <Badge className="rounded-full font-medium text-gray-500">{count}</Badge>
      )}
    </LinkTab>
  );
}
