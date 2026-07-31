import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import { useSidebar } from "@/shared/components/layout/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { classNames } from "@/shared/utils/common";

import type { MenuItem } from "@/entities/navigation/types";
import { CollapsedSidebarMenuItem } from "@/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item";
import { menuNavigationItemStyle } from "@/entities/navigation/ui/sidebar/styles";

const RecursiveInternalMenuItem: React.FC<{ item: MenuItem }> = ({ item }) => {
  if (!item.children?.length) {
    return (
      <DropdownMenuItem asChild>
        <Link to={constructPath(item.path)}>
          <Icon icon={item.icon} className="size-4" />
          {item.label}
        </Link>
      </DropdownMenuItem>
    );
  }

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <Icon icon={item.icon} className="size-4" />
        {item.label}
      </DropdownMenuSubTrigger>
      <DropdownMenuSubContent>
        {item.children.map((childItem) => (
          <RecursiveInternalMenuItem key={childItem.identifier} item={childItem} />
        ))}
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  );
};

const CollapsedMenuItemLink: React.FC<{ item: MenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} tabIndex={-1}>
    <CollapsedSidebarMenuItem icon={item.icon} tooltipContent={item.label} />
  </Link>
);

const ExpandedMenuItemLink: React.FC<{ item: MenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} className={menuNavigationItemStyle}>
    <Icon icon={item.icon} className="size-4" />
    <span className="truncate text-sm">{item.label}</span>
    <Icon
      icon="mdi:arrow-top-right"
      className="m-1 ml-auto opacity-0 group-hover/menu-item:opacity-100 group-focus/menu-item:opacity-100 group-data-[state=open]/menu-item:opacity-100"
    />
  </Link>
);

const DropdownMenuTriggerButton: React.FC<{ item: MenuItem }> = ({ item }) => {
  const { isCollapsed } = useSidebar();

  return (
    <DropdownMenuTrigger className={classNames(menuNavigationItemStyle)} asChild={isCollapsed}>
      {isCollapsed ? (
        <CollapsedSidebarMenuItem tooltipContent={item.label} icon={item.icon} />
      ) : (
        <>
          <Icon icon={item.icon} className="size-4" />
          <span className="truncate text-sm">{item.label}</span>
          <Icon
            icon="mdi:dots-vertical"
            className="m-1 ml-auto opacity-0 group-hover/menu-item:opacity-100 group-focus/menu-item:opacity-100 group-data-[state=open]/menu-item:opacity-100"
          />
        </>
      )}
    </DropdownMenuTrigger>
  );
};

export interface SidebarMenuSectionInternalProps {
  items: MenuItem[];
}

export function SidebarMenuSectionInternal({ items }: SidebarMenuSectionInternalProps) {
  const { isCollapsed } = useSidebar();

  return (
    <Col className={classNames("gap-0 p-2", isCollapsed && "items-start")}>
      {items.map((item) => {
        if (!item.children?.length) {
          return isCollapsed ? (
            <CollapsedMenuItemLink key={item.identifier} item={item} />
          ) : (
            <ExpandedMenuItemLink key={item.identifier} item={item} />
          );
        }

        return (
          <DropdownMenu key={item.identifier}>
            <DropdownMenuTriggerButton item={item} />
            <DropdownMenuContent side="left" align="start" className="min-w-50">
              {item.children.map((childItem) => (
                <RecursiveInternalMenuItem key={childItem.identifier} item={childItem} />
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </Col>
  );
}
