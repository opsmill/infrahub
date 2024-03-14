import { Disclosure } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { Circle } from "../../../components/display/circle";
import { classNames } from "../../../utils/common";
import { DropDownMenuItem } from "./desktop-menu-item";
import { MenuItem } from "./desktop-menu";

interface Props {
  title: string;
  items: MenuItem[];
  icon?: string;
  subItem?: boolean;
}

export default function DropDownMenuHeader(props: Props) {
  const { title, items, icon, subItem } = props;

  return (
    <Disclosure defaultOpen={true} as="div" className="flex flex-col">
      {({ open }) => (
        <>
          <Disclosure.Button
            className={classNames(
              "flex items-center p-3 text-gray-900 text-left text-sm font-medium group",
              subItem ? "bg-gray-50 hover:bg-gray-100" : "bg-gray-200 hover:bg-gray-300"
            )}>
            {icon ? (
              <Icon icon={icon} className="text-custom-blue-500 group-hover:text-gray-500" />
            ) : (
              <Circle className="shrink-0" />
            )}

            <span className="flex-grow truncate">{title}</span>

            <Icon
              icon="mdi:triangle-down"
              className={classNames(
                "text-[8px] group-hover:text-gray-400 mr-2.5",
                open ? "text-gray-400" : "text-gray-300 -rotate-90"
              )}
            />
          </Disclosure.Button>

          <Disclosure.Panel className="py-0.5 pl-4 space-y-1">
            {items.map((item, index: number) => {
              if (item.children?.length) {
                return (
                  <DropDownMenuHeader
                    key={index}
                    title={item.title}
                    items={item.children}
                    icon={item.icon}
                    subItem
                  />
                );
              }

              return <DropDownMenuItem key={index} {...item} />;
            })}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
