import {
  DropdownMenu,
  DropdownMenuAccordion,
  DropdownMenuAccordionContent,
  DropdownMenuAccordionTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ObjectAvatar } from "@/screens/layout/menu-navigation/components/object-avatar";
import { menuNavigationItemStyle } from "@/screens/layout/menu-navigation/styles";
import { MenuItem } from "@/screens/layout/menu-navigation/types";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

export interface MenuSectionObjectsProps {
  items: MenuItem[];
}

export function MenuSectionObject({ items }: MenuSectionObjectsProps) {
  return (
    <div className="flex flex-col">
      {items.map((item) => {
        if (!item.children || item.children.length === 0) {
          return (
            <Link to={constructPath(item.path)}>
              <Icon icon={item.icon} className="m-1 min-w-4" />
              <span className="text-sm">{item.title}</span>
            </Link>
          );
        }

        return (
          <DropdownMenu key={item.identifier}>
            <DropdownMenuTrigger className={menuNavigationItemStyle}>
              <ObjectAvatar name={item.title} />
              <span className="text-sm">{item.title}</span>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              side="left"
              align="start"
              sideOffset={12}
              className="h-[calc(100vh-57px)] min-w-[224px] px-4 py-5 bg-white border rounded-r-lg rounded-l-none shadow-none relative -top-px overflow-auto"
            >
              <h3 className="text-xl font-medium text-neutral-800 mb-5">{item.title}</h3>
              {item.children.map((child) => {
                if (!child.children || child.children.length === 0) {
                  return (
                    <DropdownMenuItem key={child.identifier} className="px-3" asChild>
                      <Link to={constructPath(child.path)}>
                        <Icon icon={child.icon} className="w-5" />
                        {child.title}
                      </Link>
                    </DropdownMenuItem>
                  );
                }

                return (
                  <DropdownMenuAccordion key={child.identifier} value={child.identifier}>
                    <DropdownMenuAccordionTrigger className={menuNavigationItemStyle}>
                      {child.title}
                    </DropdownMenuAccordionTrigger>

                    <DropdownMenuAccordionContent>
                      <DropdownMenuItem key={child.identifier} className="pl-10" asChild>
                        <Link to={constructPath(child.path)}>{child.title}</Link>
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
