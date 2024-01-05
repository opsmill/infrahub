import { Disclosure } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { Circle } from "../../components/display/circle";
import { classNames } from "../../utils/common";
import { DropDownMenuItem } from "./desktop-menu-item";

interface Props {
  title: string;
  items: React.ReactElement[];
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
              "flex flex-1 items-center group p-3 text-gray-900 text-left text-sm font-medium ",
              subItem ? "bg-gray-50 hover:bg-gray-100" : "bg-gray-200 hover:bg-gray-300"
            )}>
            {icon && (
              <Icon icon={icon} className="mr-1 text-custom-blue-500 group-hover:text-gray-500" />
            )}

            {!icon && <Circle />}

            <span className="flex-1">{title}</span>

            <svg
              className={classNames(
                open ? "text-gray-400 rotate-90" : "text-gray-300",
                "ml-3 w-4 h-4 transform transition-colors duration-150 ease-in-out group-hover:text-gray-400"
              )}
              viewBox="0 0 20 20"
              aria-hidden="true">
              <path d="M6 6L14 10L6 14V6Z" fill="currentColor" />
            </svg>
          </Disclosure.Button>

          <Disclosure.Panel className="">
            <div className="pl-4">
              {items.map((item: any, index: number) => {
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
            </div>
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
