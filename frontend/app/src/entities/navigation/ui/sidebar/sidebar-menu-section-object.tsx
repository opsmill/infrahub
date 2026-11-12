import { Popover } from "@infrahub/ui";
import React from "react";
import {
  Button as AriaButton,
  Link as AriaLink,
  DialogTrigger,
  NavigationTree,
  NavigationTreeItem,
  NavigationTreeItemContent,
} from "react-aria-components";
import { Link, useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Icon } from "@/shared/components/display/icon";
import { useSidebar } from "@/shared/components/layout/sidebar";
import { classNames } from "@/shared/utils/common";

import type { MenuItem } from "@/entities/navigation/domain/model/menu";
import { CollapsedSidebarMenuItem } from "@/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item";
import { SidebarMenuItemAvatar } from "@/entities/navigation/ui/sidebar/sidebar-menu-item-avatar";
import { menuNavigationItemStyle } from "@/entities/navigation/ui/sidebar/styles";

function MenuItemIcon({ item }: { item: MenuItem }) {
  if (item.icon) {
    return <Icon icon={item.icon} className="size-4 shrink-0" />;
  }
  return <SidebarMenuItemAvatar name={item.label} />;
}

const collectGroupIdentifiers = (items: MenuItem[]): string[] =>
  items.flatMap((item) =>
    item.children?.length ? [item.identifier, ...collectGroupIdentifiers(item.children)] : []
  );

// Each level is pushed (level + 1) * 18px past its parent, plus the 1px guide line of every level above.
const nestedIndentPx = (depth: number) => (18 * depth * (depth + 1)) / 2 + depth;

function ObjectTreeItemLabel({ item }: { item: MenuItem }) {
  return (
    <>
      <Icon icon={item.icon} className="inline-flex w-5 justify-center" />
      {item.label}
    </>
  );
}

function ObjectTreeItem({ item }: { item: MenuItem }) {
  return (
    <NavigationTreeItem
      id={item.identifier}
      textValue={item.label || item.name}
      href={item.path ? constructPath(item.path) : undefined}
      className="group/row relative cursor-default outline-hidden data-href:cursor-pointer"
    >
      <NavigationTreeItemContent>
        {({ level, hasChildItems, isExpanded }) => {
          const depth = level - 1;

          return (
            <div style={{ paddingLeft: nestedIndentPx(depth) }}>
              {Array.from({ length: depth }, (_, ancestorDepth) => (
                <span
                  key={ancestorDepth}
                  aria-hidden
                  className="absolute inset-y-0 w-px bg-border-strong"
                  style={{ left: nestedIndentPx(ancestorDepth + 1) - 1 }}
                />
              ))}

              <div
                className={classNames(
                  "flex items-center gap-2 rounded-lg px-2.5 text-sm text-subtle",
                  "group-hover/row:bg-highlight group-data-focus-visible/row:bg-highlight",
                  hasChildItems ? "py-1 font-bold text-foreground" : "py-2 font-medium"
                )}
              >
                {item.path ? (
                  <AriaLink className="flex items-center gap-2 outline-hidden">
                    <ObjectTreeItemLabel item={item} />
                  </AriaLink>
                ) : (
                  <span className="flex items-center gap-2">
                    <ObjectTreeItemLabel item={item} />
                  </span>
                )}

                {hasChildItems && (
                  <AriaButton slot="chevron" className="ml-auto flex p-1">
                    <Icon
                      icon="mdi:chevron-right"
                      className={classNames(
                        "text-xl transition-transform duration-200 motion-reduce:transition-none",
                        isExpanded && "rotate-90"
                      )}
                    />
                  </AriaButton>
                )}
              </div>
            </div>
          );
        }}
      </NavigationTreeItemContent>

      {item.children?.map((child) => (
        <ObjectTreeItem key={child.identifier} item={child} />
      ))}
    </NavigationTreeItem>
  );
}

function ObjectGroupTrigger({ item }: { item: MenuItem }) {
  const { isCollapsed } = useSidebar();

  if (isCollapsed) {
    return <CollapsedSidebarMenuItem tooltipContent={item.label} icon={item.icon} />;
  }

  return (
    <AriaButton className={menuNavigationItemStyle}>
      <MenuItemIcon item={item} />
      <span className="truncate text-sm" title={item.label}>
        {item.label}
      </span>
    </AriaButton>
  );
}

function ObjectGroup({ item }: { item: MenuItem }) {
  const groupItems = item.children ?? [];
  const location = useLocation();
  const currentLocation = location.pathname + location.search;
  const [openedAtLocation, setOpenedAtLocation] = React.useState<string | null>(null);

  return (
    <DialogTrigger
      isOpen={openedAtLocation === currentLocation} // The menu stays open only on the page it was opened from, so following any of its links closes it.
      onOpenChange={(isOpen) => setOpenedAtLocation(isOpen ? currentLocation : null)}
    >
      <ObjectGroupTrigger item={item} />

      <Popover placement="right top" className="no-scrollbar min-w-60 overflow-auto">
        <NavigationTree
          aria-label={item.label}
          defaultExpandedKeys={collectGroupIdentifiers(groupItems)}
          className="p-1"
        >
          {groupItems.map((child) => (
            <ObjectTreeItem key={child.identifier} item={child} />
          ))}
        </NavigationTree>
      </Popover>
    </DialogTrigger>
  );
}

function TopLevelMenuItem({ item }: { item: MenuItem }) {
  const { isCollapsed } = useSidebar();

  if (!item.children?.length) {
    return (
      <Link
        to={constructPath(item.path)}
        className={classNames(menuNavigationItemStyle, isCollapsed && "p-2")}
      >
        <MenuItemIcon item={item} />
        <span
          className={classNames("truncate text-sm", isCollapsed && "hidden")}
          title={item.label}
        >
          {item.label}
        </span>
      </Link>
    );
  }

  return <ObjectGroup item={item} />;
}

export interface SidebarMenuSectionObjectProps {
  items: MenuItem[];
}

export function SidebarMenuSectionObject({ items }: SidebarMenuSectionObjectProps) {
  return items.map((item) => <TopLevelMenuItem key={item.identifier} item={item} />);
}
