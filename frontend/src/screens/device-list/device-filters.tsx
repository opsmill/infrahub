import { Fragment } from "react";
import { Popover, Transition } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/20/solid";
import { classNames } from "../../App";
import FilterBranch from "./filters/filter-branch";
import FilterTime from "./filters/filter-time";
import FilterTags from "./filters/filter-tags";
import FilterStatus from "./filters/filter-status";

export default function DeviceFilters() {
  return (
    <Popover className="relative">
      {({ open }) => (
        <>
          <Popover.Button
            className={classNames(
              open ? "text-gray-900" : "text-gray-500",
              "group inline-flex items-center rounded-md bg-white text-base font-medium hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            )}
          >
            <span>Filters</span>
            <ChevronDownIcon
              className={classNames(
                open ? "text-gray-600" : "text-gray-400",
                "ml-2 h-5 w-5 group-hover:text-gray-500"
              )}
              aria-hidden="true"
            />
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
            <Popover.Panel className="absolute right-0 z-20 mt-3 w-screen max-w-sm px-2 sm:px-0 bg-white">
              <div className="overflow-hidden rounded-lg shadow-lg ring-1 ring-black ring-opacity-5 p-6 h-96">
                <FilterBranch />
                <br />
                <FilterTime />
                <br />
                <FilterTags />
                <br />
                <FilterStatus />
              </div>
            </Popover.Panel>
          </Transition>
        </>
      )}
    </Popover>
  );
}
