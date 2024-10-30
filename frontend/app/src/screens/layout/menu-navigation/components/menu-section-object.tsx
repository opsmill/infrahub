import {
  DropdownMenu,
  DropdownMenuAccordion,
  DropdownMenuAccordionContent,
  DropdownMenuAccordionTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { ObjectAvatar } from "@/screens/layout/menu-navigation/components/object-avatar";
import { menuNavigationItemStyle } from "@/screens/layout/menu-navigation/styles";
import { MenuItem } from "@/screens/layout/menu-navigation/types";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { Link } from "react-router-dom";

export interface MenuSectionObjectsProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

const MenuItemIcon: React.FC<{ item: MenuItem }> = ({ item }) => {
  if (item.icon) {
    return <Icon icon={item.icon} className="text-md m-1 min-h-4 min-w-4" />;
  }
  return <ObjectAvatar name={item.label} />;
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
          <Icon icon={item.icon} className="w-5 shrink-0 inline-flex justify-center items-center" />
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
          "font-bold py-1 data-[state=open]:bg-transparent data-[state=open]:text-inherit data-[state=open]:data-[highlighted]:bg-neutral-100"
        )}
        iconClassName="hover:bg-neutral-200"
      >
        <Icon icon={item.icon} className="w-5 shrink-0 inline-flex justify-center items-center" />
        {item.path ? (
          <Link to={constructPath(item.path)} className="text-left cursor-pointer">
            {item.label}
          </Link>
        ) : (
          item.label
        )}
      </DropdownMenuAccordionTrigger>

      <DropdownMenuAccordionContent
        style={{ marginLeft: (level + 1) * 18 }}
        className="border-l border-neutral-200"
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
      <Link to={constructPath(item.path)} className={menuNavigationItemStyle}>
        <MenuItemIcon item={item} />
        <span className={classNames("text-sm", isCollapsed && "hidden")}>{item.label}</span>
      </Link>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={classNames(menuNavigationItemStyle, isCollapsed && "p-2")}>
        <Tooltip enabled={isCollapsed} content={item.label} side="right">
          <span className="flex">
            <MenuItemIcon item={item} />
          </span>
        </Tooltip>

        <span className={classNames("text-sm truncate", isCollapsed && "hidden")}>
          {item.label}
        </span>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="left"
        align="start"
        sideOffset={isCollapsed ? 6 : 12}
        className="h-[calc(100vh-57px)] mt-[57px] min-w-[275px] px-4 py-5 bg-white border rounded-r-lg rounded-l-none shadow-none relative -top-px overflow-auto data-[side=right]:slide-in-from-left-[100px]"
      >
        <h3 className="text-xl font-medium text-neutral-800 mb-5">{item.label}</h3>
        {item.children.map((child) => (
          <RecursiveObjectMenuItem key={child.identifier} item={child} isCollapsed={isCollapsed} />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const MenuSectionObject: React.FC<MenuSectionObjectsProps> = ({ isCollapsed, items }) => (
  <div className="flex flex-col w-full overflow-auto">
    {items.map((item) => (
      <TopLevelMenuItem key={item.identifier} item={item} isCollapsed={isCollapsed} />
    ))}
  </div>
);
