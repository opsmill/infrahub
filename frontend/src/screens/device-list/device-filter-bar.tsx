import { Fragment } from "react";
import { Disclosure, Menu, Transition } from "@headlessui/react";
import { ChevronDownIcon, FunnelIcon } from "@heroicons/react/20/solid";
import { classNames } from "../../App";
import FilterBranch from "./filters/filter-branch";
import FilterTime from "./filters/filter-time";
import FilterTags from "./filters/filter-tags";
import FilterStatus from "./filters/filter-status";

const sortOptions = [
  { name: "Name", href: "#", current: true },
  { name: "Status", href: "#", current: false },
  { name: "ASN", href: "#", current: false },
];

const activeFilters = [
  { value: "status", label: "Active" },
  { value: "role", label: "Edge" },
];

export default function DeviceFilterBar() {
  return (
    <div className="bg-white">
      <Disclosure
        as="section"
        aria-labelledby="filter-heading"
        className="grid items-center border-t border-b border-gray-200"
      >
        <h2 id="filter-heading" className="sr-only">
          Filters
        </h2>
        <div className="bg-gray-100">
          <div className="mx-auto py-3 sm:flex sm:items-center sm:px-6 lg:px-8">
            <div className="flex space-x-6 divide-x divide-gray-200 text-sm">
              <div>
                <Disclosure.Button className="group flex items-center font-medium text-blue-500">
                  <FunnelIcon
                    className="mr-2 h-5 w-5 flex-none text-blue-400 group-hover:text-blue-500"
                    aria-hidden="true"
                  />
                  2 Filters
                </Disclosure.Button>
              </div>
              <div className="pl-6">
                <button type="button" className="text-gray-500">
                  Clear all
                </button>
              </div>
            </div>
            <div
              aria-hidden="true"
              className="hidden h-5 w-px bg-gray-300 sm:ml-4 sm:block"
            />

            <div className="mt-2 flex-1 sm:mt-0 sm:ml-4">
              <div className="-m-1 flex flex-wrap items-center">
                {activeFilters.map((activeFilter) => (
                  <span
                    key={activeFilter.value}
                    className="m-1 inline-flex items-center rounded-full border border-gray-200 bg-white py-1.5 pl-3 pr-2 text-sm font-medium text-gray-900"
                  >
                    <span>{activeFilter.label}</span>
                    <button
                      type="button"
                      className="ml-1 inline-flex h-4 w-4 flex-shrink-0 rounded-full p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-500"
                    >
                      <span className="sr-only">
                        Remove filter for {activeFilter.label}
                      </span>
                      <svg
                        className="h-2 w-2"
                        stroke="currentColor"
                        fill="none"
                        viewBox="0 0 8 8"
                      >
                        <path
                          strokeLinecap="round"
                          strokeWidth="1.5"
                          d="M1 1l6 6m0-6L1 7"
                        />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div className="flex justify-end">
              <Menu as="div" className="relative inline-block">
                <div className="flex">
                  <Menu.Button className="group inline-flex justify-center text-sm font-medium text-gray-700 hover:text-gray-900">
                    Sort
                    <ChevronDownIcon
                      className="-mr-1 ml-1 h-5 w-5 flex-shrink-0 text-gray-400 group-hover:text-gray-500"
                      aria-hidden="true"
                    />
                  </Menu.Button>
                </div>

                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 z-20 mt-2 w-40 origin-top-right rounded-md bg-white shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none">
                    <div className="py-1">
                      {sortOptions.map((option) => (
                        <Menu.Item key={option.name}>
                          {({ active }) => (
                            <a
                              href={option.href}
                              className={classNames(
                                option.current
                                  ? "font-medium text-gray-900"
                                  : "text-gray-500",
                                active ? "bg-gray-100" : "",
                                "block px-4 py-2 text-sm"
                              )}
                            >
                              {option.name}
                            </a>
                          )}
                        </Menu.Item>
                      ))}
                    </div>
                  </Menu.Items>
                </Transition>
              </Menu>
            </div>
          </div>
        </div>
        <Disclosure.Panel className="border-t border-gray-200 pb-10">
          <div className="mx-auto max-w-7xl px-4 text-sm sm:px-6">
            <div className="mt-6 grid grid-cols-1 gap-y-6 gap-x-10 sm:grid-cols-6">
              <div className="sm:col-span-2">
                <FilterBranch />
              </div>

              <div className="sm:col-span-2">
                <FilterTime />
              </div>

              <div className="sm:col-span-2">
                <FilterTags />
              </div>

              <div className="sm:col-span-2">
                <label
                  htmlFor="asn"
                  className="block text-sm font-medium text-gray-700"
                >
                  ASN
                </label>
                <div className="mt-1">
                  <input
                    type="text"
                    name="asn"
                    id="asn"
                    autoComplete="address-level2"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </div>

              <div className="sm:col-span-2">
                <label
                  htmlFor="site"
                  className="block text-sm font-medium text-gray-700"
                >
                  Site
                </label>
                <div className="mt-1">
                  <input
                    type="text"
                    name="site"
                    id="site"
                    autoComplete="site"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </div>

              <div className="sm:col-span-2">
                <FilterStatus />
              </div>
            </div>
          </div>
        </Disclosure.Panel>
      </Disclosure>
    </div>
  );
}
