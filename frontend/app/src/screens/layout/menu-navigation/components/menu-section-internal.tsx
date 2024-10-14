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
import { MenuItem } from "@/screens/layout/menu-navigation/types";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

export interface MenuSectionInternalProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

export function MenuSectionInternal({ items, isCollapsed }: MenuSectionInternalProps) {
  return (
    <div className="flex flex-col mb-auto">
      {items.map((item) => {
        if (!item.children || item.children.length === 0) {
          if (isCollapsed) {
            return (
              <Link to={constructPath(item.path)}>
                <CollapsedButton
                  icon={item.icon}
                  tooltipContent={item.label}
                  key={item.identifier}
                />
              </Link>
            );
          }
          return (
            <Link to={constructPath(item.path)} className={menuNavigationItemStyle}>
              <Icon icon={item.icon} className="m-1 min-w-4" />
              <span className="text-sm truncate">{item.label}</span>
            </Link>
          );
        }

        return (
          <DropdownMenu key={item.identifier}>
            <DropdownMenuTrigger
              className={classNames(menuNavigationItemStyle, isCollapsed && "p-0")}
            >
              {isCollapsed ? (
                <CollapsedButton tooltipContent={item.label} icon={item.icon} className="p-0" />
              ) : (
                <>
                  <Icon icon={item.icon} className="text-lg min-w-4" />
                  <span className="text-sm truncate">{item.label}</span>
                  <Icon
                    icon="mdi:dots-vertical"
                    className="m-1 ml-auto opacity-0 group-hover:opacity-100 group-focus:opacity-100 group-data-[state=open]:opacity-100"
                  />
                </>
              )}
            </DropdownMenuTrigger>

            <DropdownMenuContent side="left" align="start" className="min-w-[200px]">
              {item.children.map((child) => {
                if (!child.children || child.children.length === 0) {
                  return (
                    <DropdownMenuItem key={child.identifier} asChild>
                      <Link to={constructPath(child.path)}>{child.label}</Link>
                    </DropdownMenuItem>
                  );
                }

                return (
                  <DropdownMenuSub key={child.identifier}>
                    <DropdownMenuSubTrigger>{item.label}</DropdownMenuSubTrigger>

                    <DropdownMenuSubContent>
                      {child.children.map((grandchild) => {
                        return (
                          <DropdownMenuItem key={grandchild.identifier} asChild>
                            <Link to={constructPath(grandchild.path)}>{grandchild.label}</Link>
                          </DropdownMenuItem>
                        );
                      })}
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
}
