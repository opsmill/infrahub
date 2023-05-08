// type PopOver = {}

import { Popover, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { classNames } from "../utils/common";

export const PopOver = ({
  children,
  className,
  buttonComponent,
  title,
}: any) => {
  return (
    <Popover className="flex relative">
      <Popover.Button as="div" className="flex">
        {buttonComponent}
      </Popover.Button>

      <Transition
        as={Fragment}
        enter="transition ease-out duration-200"
        enterFrom="opacity-0 translate-y-1"
        enterTo="opacity-100 translate-y-0"
        leave="transition ease-in duration-150"
        leaveFrom="opacity-100 translate-y-0"
        leaveTo="opacity-0 translate-y-1"
      >
        <Popover.Panel
          className={classNames(
            "absolute bg-white z-10 rounded-lg border shadow-xl mt-3 w-screen max-w-sm grid grid-cols-1 divide-y divide-gray-200",
            className
          )}
        >
          {({ close }) => (
            <>
              {title && (
                <div className="font-semibold text-center p-4">{title}</div>
              )}

              <div className="p-4">{children({ close })}</div>
            </>
          )}
        </Popover.Panel>
      </Transition>
    </Popover>
  );
};
