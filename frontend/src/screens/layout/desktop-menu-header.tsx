import { Disclosure } from "@headlessui/react";
import React from "react";
import { Circle } from "../../components/circle";
import { classNames } from "../../utils/common";
import { DropDownMenuItem } from "./desktop-menu-item";

interface Props {
  title: string;
  items: React.ReactElement[];
  Icon?: React.ComponentType<any>;
}

export default function DropDownMenuHeader(props: Props) {
  const { title, items, Icon } = props;

  return (
    <Disclosure defaultOpen={true} as="div" className="flex flex-col">
      {({ open }) => (
        <>
          <Disclosure.Button
            className={
              "flex flex-1 items-center group p-1 my-1 bg-gray-100 text-gray-900 text-left text-sm font-medium rounded-md"
            }>
            {Icon && (
              <Icon
                className="mr-3 h-6 w-6 flex-shrink-0 text-custom-blue-500 group-hover:text-gray-500"
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
                if (item.children) {
                  return (
                    <DropDownMenuHeader key={index} title={item.title} items={item.children} />
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
