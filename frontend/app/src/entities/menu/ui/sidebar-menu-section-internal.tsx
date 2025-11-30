import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
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

import type { MenuItem } from "@/entities/menu/types";
import { CollapsedSidebarMenuItem } from "@/entities/menu/ui/collapsed-sidebar-menu-item";
import { menuNavigationItemStyle } from "@/entities/menu/ui/styles";

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
  <Link to={constructPath(item.path)} className={classNames(menuNavigationItemStyle, "h-10")}>
    <Icon icon={item.icon} className="size-4" />
    <span className="truncate text-sm">{item.label}</span>
    <Icon
      icon="mdi:arrow-top-right"
      className="m-1 ml-auto text-sm opacity-0 group-hover:opacity-100 group-focus:opacity-100 group-data-[state=open]:opacity-100"
    />
  </Link>
);

const DropdownMenuTriggerButton: React.FC<{ item: MenuItem; isCollapsed: boolean }> = ({
  item,
  isCollapsed,
}) => (
  <DropdownMenuTrigger
    className={classNames(menuNavigationItemStyle, isCollapsed && "p-0")}
    asChild={isCollapsed}
  >
    {isCollapsed ? (
      <CollapsedSidebarMenuItem tooltipContent={item.label} icon={item.icon} />
    ) : (
      <>
        <Icon icon={item.icon} className="size-4" />
        <span className="truncate text-sm">{item.label}</span>
        <Icon
          icon="mdi:dots-vertical"
          className="m-1 ml-auto opacity-0 group-hover:opacity-100 group-focus:opacity-100 group-data-[state=open]:opacity-100"
        />
      </>
    )}
  </DropdownMenuTrigger>
);

export interface SidebarMenuSectionInternalProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

export function SidebarMenuSectionInternal({
  items,
  isCollapsed,
}: SidebarMenuSectionInternalProps) {
  return (
    <div className="mb-auto flex flex-col">
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
            <DropdownMenuTriggerButton item={item} isCollapsed={!!isCollapsed} />
            <DropdownMenuContent side="left" align="start" className="min-w-[200px]">
              {item.children.map((childItem) => (
                <RecursiveInternalMenuItem key={childItem.identifier} item={childItem} />
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
}
