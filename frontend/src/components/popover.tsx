// type PopOver = {}

import { Popover, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { classNames } from "../utils/common";

export enum POPOVER_SIZE {
  SMALL,
  MEDIUM,
  LARGE,
}

type PopoverPros = {
  children?: any;
  className?: string;
  buttonComponent?: any;
  title?: string;
  disabled?: boolean;
  size?: POPOVER_SIZE;
};

const sizesClass = {
  [POPOVER_SIZE.SMALL]: "w-[300px]",
  [POPOVER_SIZE.MEDIUM]: "w-[500px]",
  [POPOVER_SIZE.LARGE]: "w-[700px]",
};

// Stop propagation for clicks
const preventClick = (event: any) => {
  event?.preventDefault();
  event?.stopPropagation();
};

export const PopOver = ({
  children,
  className,
  buttonComponent,
  title,
  disabled,
  size,
}: PopoverPros) => {
  return (
    <Popover className="flex relative" onClick={preventClick}>
      <Popover.Button as="div" className="flex" disabled={disabled}>
        {buttonComponent}
      </Popover.Button>

      <Transition
        as={Fragment}
        enter="transition ease-out duration-200"
        enterFrom="opacity-0 translate-y-1"
        enterTo="opacity-100 translate-y-0"
        leave="transition ease-in duration-150"
        leaveFrom="opacity-100 translate-y-0"
        leaveTo="opacity-0 translate-y-1">
        <Popover.Panel
          className={classNames(
            "absolute z-10 rounded-lg border shadow-xl right-0 top-10 mt-3 grid grid-cols-1 divide-y divide-gray-200",
            className?.includes("bg-") ? "" : "bg-custom-white",
            className ?? "",
            sizesClass[size ?? POPOVER_SIZE.SMALL]
          )}>
          {({ close }) => (
            <>
              {title && <div className="font-semibold text-center p-4">{title}</div>}

              <div className="p-4">{children({ close })}</div>
            </>
          )}
        </Popover.Panel>
      </Transition>
    </Popover>
  );
};
