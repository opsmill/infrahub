import { Disclosure } from "@headlessui/react";
import React from "react";
import { classNames } from "../../utils/common";

interface Props {
  title: string;
  items: React.ReactElement[];
  Icon: React.ComponentType<any>;
}

export default function DropDownMenuHeader(props: Props) {
  const { title, items, Icon } = props;

  return (
    <Disclosure defaultOpen={true} as="div" className="space-y-1">
      {({ open }) => (
        <>
          <Disclosure.Button
            className={classNames(
              "bg-gray-100 text-gray-900",
              "group w-full flex items-center pl-2 pr-1 py-2 text-left text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-custom-blue-500"
            )}>
            <Icon
              className="mr-3 h-6 w-6 flex-shrink-0 text-custom-blue-500 group-hover:text-gray-500"
              aria-hidden="true"
            />
            <span className="flex-1">{title}</span>
            <svg
              className={classNames(
                open ? "text-gray-400 rotate-90" : "text-gray-300",
                "ml-3 h-5 w-5 flex-shrink-0 transform transition-colors duration-150 ease-in-out group-hover:text-gray-400"
              )}
              viewBox="0 0 20 20"
              aria-hidden="true">
              <path d="M6 6L14 10L6 14V6Z" fill="currentColor" />
            </svg>
          </Disclosure.Button>
          <Disclosure.Panel className="space-y-1">{items}</Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
