import { Menu, MenuItem, MenuTrigger, Popover, SubmenuTrigger } from "@infrahub/ui";
import type React from "react";
import { Button as AriaButton } from "react-aria-components";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import { useSidebar } from "@/shared/components/layout/sidebar";
import { classNames } from "@/shared/utils/common";

import type { MenuItem as NavigationMenuItem } from "@/entities/navigation/domain/model/menu";
import { CollapsedSidebarMenuItem } from "@/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item";
import { menuNavigationItemStyle } from "@/entities/navigation/ui/sidebar/styles";

const RecursiveInternalMenuItem: React.FC<{ item: NavigationMenuItem }> = ({ item }) => {
  if (!item.children?.length) {
    return (
      <MenuItem href={constructPath(item.path)} textValue={item.label}>
        <Icon icon={item.icon} className="size-4" />
        {item.label}
      </MenuItem>
    );
  }

  return (
    <SubmenuTrigger>
      <MenuItem textValue={item.label}>
        <Icon icon={item.icon} className="size-4" />
        {item.label}
      </MenuItem>
      <Popover>
        <Menu>
          {item.children.map((childItem) => (
            <RecursiveInternalMenuItem key={childItem.identifier} item={childItem} />
          ))}
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
};

const CollapsedMenuItemLink: React.FC<{ item: NavigationMenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} tabIndex={-1}>
    <CollapsedSidebarMenuItem icon={item.icon} tooltipContent={item.label} />
  </Link>
);

const ExpandedMenuItemLink: React.FC<{ item: NavigationMenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} className={menuNavigationItemStyle}>
    <Icon icon={item.icon} className="size-4" />
    <span className="truncate text-sm">{item.label}</span>
    <Icon
      icon="mdi:arrow-top-right"
      className="m-1 ml-auto opacity-0 group-hover/menu-item:opacity-100 group-focus/menu-item:opacity-100 group-data-[state=open]/menu-item:opacity-100"
    />
  </Link>
);

const MenuTriggerButton: React.FC<{ item: NavigationMenuItem }> = ({ item }) => {
  const { isCollapsed } = useSidebar();

  if (isCollapsed) {
    return <CollapsedSidebarMenuItem tooltipContent={item.label} icon={item.icon} />;
  }

  return (
    <AriaButton className={menuNavigationItemStyle}>
      <Icon icon={item.icon} className="size-4" />
      <span className="truncate text-sm">{item.label}</span>
      <Icon
        icon="mdi:dots-vertical"
        className="m-1 ml-auto opacity-0 group-hover/menu-item:opacity-100 group-focus/menu-item:opacity-100 group-aria-expanded/menu-item:opacity-100"
      />
    </AriaButton>
  );
};

export interface SidebarMenuSectionInternalProps {
  items: NavigationMenuItem[];
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
          <MenuTrigger key={item.identifier}>
            <MenuTriggerButton item={item} />
            <Popover placement="right top" className="min-w-50">
              <Menu variant="picker" aria-label={item.label}>
                {item.children.map((childItem) => (
                  <RecursiveInternalMenuItem key={childItem.identifier} item={childItem} />
                ))}
              </Menu>
            </Popover>
          </MenuTrigger>
        );
      })}
    </Col>
  );
}
