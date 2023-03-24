// type PopOver = {}

import { Popover, Transition } from "@headlessui/react"
import { Fragment } from "react"
import { classNames } from "../utils/common"

export const PopOver = ({label, children, className}: any) => {
  return (
    <Popover className="relative">
      <Popover.Button>
        {label}
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
        <Popover.Panel className={classNames("absolute rounded-md right-0 mt-3 p-2 bg-white", className)}>
          {children}
        </Popover.Panel>
      </Transition>
    </Popover>
  )
}