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
import { Link } from "react-router-dom";

export interface MenuSectionObjectsProps {
  items: MenuItem[];
  isCollapsed?: boolean;
}

export function MenuSectionObject({ isCollapsed, items }: MenuSectionObjectsProps) {
  return (
    <div className="flex flex-col w-full overflow-auto">
      {items.map((item) => {
        if (!item.children || item.children.length === 0) {
          return (
            <Link to={constructPath(item.path)} className={menuNavigationItemStyle}>
              {item.icon ? (
                <Icon icon={item.icon} className="text-md m-1 min-h-4 min-w-4" />
              ) : (
                <ObjectAvatar name={item.label} />
              )}
              <span className={classNames("text-sm", isCollapsed && "hidden")}>{item.label}</span>
            </Link>
          );
        }

        return (
          <DropdownMenu key={item.identifier}>
            <Tooltip enabled={isCollapsed} content={item.label} side="right">
              <DropdownMenuTrigger className={menuNavigationItemStyle}>
                {item.icon ? (
                  <Icon icon={item.icon} className="text-md m-1 min-h-4 min-w-4" />
                ) : (
                  <ObjectAvatar name={item.label} />
                )}
                <span className={classNames("text-sm", isCollapsed && "hidden")}>{item.label}</span>
              </DropdownMenuTrigger>
            </Tooltip>

            <DropdownMenuContent
              side="left"
              align="start"
              sideOffset={12}
              className="h-[calc(100vh-57px)] mt-[57px] min-w-[224px] px-4 py-5 bg-white border rounded-r-lg rounded-l-none shadow-none relative -top-px overflow-auto data-[side=right]:slide-in-from-left-[100px]"
            >
              <h3 className="text-xl font-medium text-neutral-800 mb-5">{item.label}</h3>
              {item.children.map((child) => {
                if (!child.children || child.children.length === 0) {
                  return (
                    <DropdownMenuItem key={child.identifier} className="px-3" asChild>
                      <Link to={constructPath(child.path)}>
                        <Icon icon={child.icon} className="w-5" />
                        {child.label}
                      </Link>
                    </DropdownMenuItem>
                  );
                }

                return (
                  <DropdownMenuAccordion key={child.identifier} value={child.identifier}>
                    <DropdownMenuAccordionTrigger className={menuNavigationItemStyle}>
                      {child.label}
                    </DropdownMenuAccordionTrigger>

                    <DropdownMenuAccordionContent>
                      <DropdownMenuItem key={child.identifier} className="pl-10" asChild>
                        <Link to={constructPath(child.path)}>{child.label}</Link>
                      </DropdownMenuItem>
                    </DropdownMenuAccordionContent>
                  </DropdownMenuAccordion>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
}
