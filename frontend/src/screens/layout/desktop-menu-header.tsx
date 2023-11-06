import { Disclosure } from "@headlessui/react";
import * as HIcons from "@heroicons/react/24/outline";
import React from "react";
import { Circle } from "../../components/circle";
import { classNames } from "../../utils/common";
import { capitalizeFirstLetter, concatString } from "../../utils/string";
import { DropDownMenuItem } from "./desktop-menu-item";

const { ...icons } = HIcons;

interface Props {
  title: string;
  items: React.ReactElement[];
  icon?: string;
  subItem?: boolean;
}

const getIconName = (icon: string = "") =>
  `${icon.split("-").map(capitalizeFirstLetter).reduce(concatString, "")}Icon`;

export default function DropDownMenuHeader(props: Props) {
  const { title, items, icon, subItem } = props;

  // @ts-ignore
  const Icon: React.ReactElement = icon ? icons[getIconName(icon)] : null;

  return (
    <Disclosure defaultOpen={true} as="div" className="flex flex-col">
      {({ open }) => (
        <>
          <Disclosure.Button
            className={classNames(
              "flex flex-1 items-center group p-3 text-gray-900 text-left text-sm font-medium ",
              subItem ? "bg-gray-50 hover:bg-gray-100" : "bg-gray-200 hover:bg-gray-300"
            )}>
            {Icon && (
              // @ts-ignore
              <Icon
                className="m-1 h-4 w-4 flex-shrink-0 text-custom-blue-500 group-hover:text-gray-500"
                aria-hidden="true"
              />
            )}

            {!Icon && <Circle />}

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

                return <DropDownMenuItem key={index} title={item.title} path={item.path} />;
              })}
            </div>
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
