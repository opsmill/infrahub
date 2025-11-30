import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import {
  DropdownMenu,
  DropdownMenuAccordion,
  DropdownMenuAccordionContent,
  DropdownMenuAccordionTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import type { MenuItem } from "@/entities/menu/types";
import { SidebarMenuItemAvatar } from "@/entities/menu/ui/sidebar-menu-item-avatar";
import { menuNavigationItemStyle } from "@/entities/menu/ui/styles";

const MenuItemIcon: React.FC<{ item: MenuItem }> = ({ item }) => {
  if (item.icon) {
    return <Icon icon={item.icon} className="m-1 size-4 text-md" />;
  }
  return <SidebarMenuItemAvatar name={item.label} />;
};

const RecursiveObjectMenuItem: React.FC<{
  item: MenuItem;
  isCollapsed?: boolean;
  level?: number;
}> = ({ item, isCollapsed, level = 0 }) => {
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
          <RecursiveObjectMenuItem
            key={child.identifier}
            item={child}
            isCollapsed={isCollapsed}
            level={level + 1}
          />
        ))}
      </DropdownMenuAccordionContent>
    </DropdownMenuAccordion>
  );
};

const TopLevelMenuItem: React.FC<{
  item: MenuItem;
  isCollapsed?: boolean;
}> = ({ item, isCollapsed }) => {
  if (!item.children?.length) {
    return (
      <Link
        to={constructPath(item.path)}
        className={classNames(menuNavigationItemStyle, isCollapsed ? "p-2" : "w-[224px]")}
      >
        <MenuItemIcon item={item} />
        <span className={classNames("text-sm", isCollapsed && "hidden")}>{item.label}</span>
      </Link>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={classNames(menuNavigationItemStyle, isCollapsed ? "p-2" : "w-[224px]")}
      >
        <Tooltip enabled={isCollapsed} content={item.label} side="right">
          <span className="flex">
            <MenuItemIcon item={item} />
          </span>
        </Tooltip>

        <span className={classNames("truncate text-sm", isCollapsed && "hidden")}>
          {item.label}
        </span>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="left"
        align="start"
        sideOffset={isCollapsed ? 6 : 12}
        className="max-h-[calc(100vh-7rem)] min-w-60 overflow-auto"
      >
        {item.children.map((child) => (
          <RecursiveObjectMenuItem key={child.identifier} item={child} isCollapsed={isCollapsed} />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export interface SidebarMenuSectionObjectProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

export function SidebarMenuSectionObject({ isCollapsed, items }: SidebarMenuSectionObjectProps) {
  return items.map((item) => (
    <TopLevelMenuItem key={item.identifier} item={item} isCollapsed={isCollapsed} />
  ));
}
