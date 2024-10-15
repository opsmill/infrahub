import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CollapsedButton } from "@/screens/layout/menu-navigation/components/collapsed-button";
import { menuNavigationItemStyle } from "@/screens/layout/menu-navigation/styles";
import type { MenuItem } from "@/screens/layout/menu-navigation/types";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { Link } from "react-router-dom";

export interface MenuSectionInternalProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

const RecursiveDropdownMenuItem: React.FC<{ item: MenuItem }> = ({ item }) => {
  if (!item.children?.length) {
    return (
      <DropdownMenuItem key={item.identifier} asChild>
        <Link to={constructPath(item.path)}>{item.label}</Link>
      </DropdownMenuItem>
    );
  }

  return (
    <DropdownMenuSub key={item.identifier}>
      <DropdownMenuSubTrigger>{item.label}</DropdownMenuSubTrigger>
      <DropdownMenuSubContent>
        {item.children.map((childItem) => (
          <RecursiveDropdownMenuItem key={childItem.identifier} item={childItem} />
        ))}
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  );
};

const CollapsedMenuItemLink: React.FC<{ item: MenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} key={item.identifier}>
    <CollapsedButton icon={item.icon} tooltipContent={item.label} />
  </Link>
);

const ExpandedMenuItemLink: React.FC<{ item: MenuItem }> = ({ item }) => (
  <Link to={constructPath(item.path)} className={menuNavigationItemStyle} key={item.identifier}>
    <Icon icon={item.icon} className="min-w-4" />
    <span className="text-sm truncate">{item.label}</span>
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
      <CollapsedButton tooltipContent={item.label} icon={item.icon} />
    ) : (
      <>
        <Icon icon={item.icon} className="min-w-4" />
        <span className="text-sm truncate">{item.label}</span>
        <Icon
          icon="mdi:dots-vertical"
          className="m-1 ml-auto opacity-0 group-hover:opacity-100 group-focus:opacity-100 group-data-[state=open]:opacity-100"
        />
      </>
    )}
  </DropdownMenuTrigger>
);

export function MenuSectionInternal({ items, isCollapsed }: MenuSectionInternalProps) {
  return (
    <div className="flex flex-col mb-auto">
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
                <RecursiveDropdownMenuItem key={childItem.identifier} item={childItem} />
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
}
