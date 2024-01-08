// type PopOver = {}

import { Popover, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { classNames } from "../../utils/common";

export enum POPOVER_SIZE {
  NONE,
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
  width?: POPOVER_SIZE;
  height?: POPOVER_SIZE;
};

const widthClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "w-[300px]",
  [POPOVER_SIZE.MEDIUM]: "w-[500px]",
  [POPOVER_SIZE.LARGE]: "w-[800px]",
};

const heightClass = {
  [POPOVER_SIZE.NONE]: "",
  [POPOVER_SIZE.SMALL]: "h-[300px]",
  [POPOVER_SIZE.MEDIUM]: "h-[500px]",
  [POPOVER_SIZE.LARGE]: "h-[800px]",
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
  width,
  height,
}: PopoverPros) => {
  return (
    <Popover className="relative" onClick={preventClick}>
      <Popover.Button as="div" disabled={disabled}>
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
            "absolute z-10 overflow-scroll rounded-lg border shadow-xl grid grid-cols-1 divide-y divide-gray-200",
            className?.includes("bg-") ? "" : "bg-custom-white",
            className?.includes("right-") ? "" : "right-0",
            className?.includes("top-") ? "" : "top-10",
            className?.includes("mt-") ? "" : "mt-3",
            className ?? "",
            widthClass[width ?? POPOVER_SIZE.SMALL],
            heightClass[height ?? POPOVER_SIZE.SMALL]
          )}>
          {({ close }) => (
            <>
              {title && <div className="font-semibold text-center p-2">{title}</div>}

              <div className="p-2">{children({ close })}</div>
            </>
          )}
        </Popover.Panel>
      </Transition>
    </Popover>
  );
};
