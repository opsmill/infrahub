import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { useSidebar } from "@/shared/components/layout/sidebar";
import {
  DropdownMenu,
  DropdownMenuAccordion,
  DropdownMenuAccordionContent,
  DropdownMenuAccordionTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { classNames } from "@/shared/utils/common";

import type { MenuItem } from "@/entities/navigation/types";
import { CollapsedSidebarMenuItem } from "@/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item";
import { SidebarMenuItemAvatar } from "@/entities/navigation/ui/sidebar/sidebar-menu-item-avatar";
import { menuNavigationItemStyle } from "@/entities/navigation/ui/sidebar/styles";

const MenuItemIcon: React.FC<{ item: MenuItem }> = ({ item }) => {
  if (item.icon) {
    return <Icon icon={item.icon} className="size-4" />;
  }
  return <SidebarMenuItemAvatar name={item.label} />;
};

const RecursiveObjectMenuItem: React.FC<{
  item: MenuItem;
  level?: number;
}> = ({ item, level = 0 }) => {
  if (!item.children?.length) {
    return (
      <DropdownMenuItem className={menuNavigationItemStyle} asChild>
        <Link to={constructPath(item.path)}>
          <Icon icon={item.icon} className="inline-flex w-5 shrink-0 items-center justify-center" />
          {item.label}
        </Link>
      </DropdownMenuItem>
    );
  }

  return (
    <DropdownMenuAccordion value={item.identifier} defaultOpen>
      <DropdownMenuAccordionTrigger
        className={classNames(
          menuNavigationItemStyle,
          "py-1 font-bold data-[state=open]:data-highlighted:bg-neutral-100 data-[state=open]:bg-transparent data-[state=open]:text-inherit"
        )}
        iconClassName="hover:bg-neutral-200"
      >
        <Icon icon={item.icon} className="inline-flex w-5 shrink-0 items-center justify-center" />
        {item.path ? (
          <Link to={constructPath(item.path)} className="cursor-pointer text-left">
            {item.label}
          </Link>
        ) : (
          item.label
        )}
      </DropdownMenuAccordionTrigger>

      <DropdownMenuAccordionContent
        style={{ marginLeft: (level + 1) * 18 }}
        className="border-neutral-200 border-l"
      >
        {item.children.map((child) => (
          <RecursiveObjectMenuItem key={child.identifier} item={child} level={level + 1} />
        ))}
      </DropdownMenuAccordionContent>
    </DropdownMenuAccordion>
  );
};

const TopLevelMenuItem: React.FC<{
  item: MenuItem;
}> = ({ item }) => {
  const { isCollapsed } = useSidebar();

  if (!item.children?.length) {
    return (
      <Link
        to={constructPath(item.path)}
        className={classNames(menuNavigationItemStyle, isCollapsed ? "p-2" : "w-full")}
      >
        <MenuItemIcon item={item} />
        <span className={classNames("text-sm", isCollapsed && "hidden")}>{item.label}</span>
      </Link>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={classNames(menuNavigationItemStyle, isCollapsed ? "p-2" : "w-full")}
        asChild={isCollapsed}
      >
        {isCollapsed ? (
          <CollapsedSidebarMenuItem tooltipContent={item.label} icon={item.icon} />
        ) : (
          <>
            <MenuItemIcon item={item} />
            <span className="truncate text-sm">{item.label}</span>
          </>
        )}
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="left"
        align="start"
        className="max-h-[calc(100vh-7rem)] min-w-60 overflow-auto"
      >
        {item.children.map((child) => (
          <RecursiveObjectMenuItem key={child.identifier} item={child} />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export interface SidebarMenuSectionObjectProps {
  items: MenuItem[];
}

export function SidebarMenuSectionObject({ items }: SidebarMenuSectionObjectProps) {
  return items.map((item) => <TopLevelMenuItem key={item.identifier} item={item} />);
}
