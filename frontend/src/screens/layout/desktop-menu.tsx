import { Disclosure } from "@headlessui/react";
import { LinkIcon, UserIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { Link, NavLink } from "react-router-dom";
import { classNames } from "../../App";
import { comboxBoxFilterState } from "../../state/atoms/filters.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import LoadingScreen from "../loading-screen/loading-screen";

import logo from "./logo.png";

export default function DesktopMenu() {
  const [schema] = useAtom(schemaState);
  const [, setCurrentFilters] = useAtom(comboxBoxFilterState);
  return (
    <div className="hidden md:fixed md:inset-y-0 md:flex md:w-64 md:flex-col z-20">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-white pt-5">
        <div className="flex flex-shrink-0 items-center px-4">
          <img className="h-10 w-auto" src={logo} alt="Your Company" />
        </div>
        <div className="mt-5 flex flex-grow flex-col flex-1 overflow-auto py-2">
          <nav className="flex-1 space-y-2 bg-white px-2" aria-label="Sidebar">
            <Disclosure defaultOpen={true} as="div" className="space-y-1">
              {({ open }) => (
                <>
                  <Disclosure.Button
                    className={classNames(
                      false
                        ? "bg-gray-100 text-gray-900"
                        : "bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                      "group w-full flex items-center pl-2 pr-1 py-2 text-left text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    )}
                  >
                    <LinkIcon
                      className="mr-3 h-6 w-6 flex-shrink-0 text-blue-400 group-hover:text-gray-500"
                      aria-hidden="true"
                    />
                    <span className="flex-1">Objects</span>
                    <svg
                      className={classNames(
                        open ? "text-gray-400 rotate-90" : "text-gray-300",
                        "ml-3 h-5 w-5 flex-shrink-0 transform transition-colors duration-150 ease-in-out group-hover:text-gray-400"
                      )}
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                    >
                      <path d="M6 6L14 10L6 14V6Z" fill="currentColor" />
                    </svg>
                  </Disclosure.Button>
                  <Disclosure.Panel className="space-y-1">
                    {schema.map((item) => (
                      <NavLink
                        to={`/objects/${item.name}`}
                        key={item.name}
                        onClick={() => setCurrentFilters([])}
                      >
                        {({ isActive }) => (
                          <div
                            key={item.name}
                            className={classNames(
                              "group flex w-full items-center rounded-md py-2 pl-11 pr-2 text-sm font-medium text-gray-600",
                              isActive
                                ? "bg-gray-300"
                                : "hover:bg-gray-50 hover:text-gray-900"
                            )}
                          >
                            {item.label}
                          </div>
                        )}
                      </NavLink>
                    ))}
                  </Disclosure.Panel>
                </>
              )}
            </Disclosure>
            {schema.length === 0 && <LoadingScreen hideText={true} size="10" />}
            <Disclosure defaultOpen={true} as="div" className="space-y-1">
              {({ open }) => (
                <>
                  <Disclosure.Button
                    className={classNames(
                      false
                        ? "bg-gray-100 text-gray-900"
                        : "bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                      "group w-full flex items-center pl-2 pr-1 py-2 text-left text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    )}
                  >
                    <UserIcon
                      className="mr-3 h-6 w-6 flex-shrink-0 text-blue-400 group-hover:text-gray-500"
                      aria-hidden="true"
                    />
                    <span className="flex-1">Admin</span>
                    <svg
                      className={classNames(
                        open ? "text-gray-400 rotate-90" : "text-gray-300",
                        "ml-3 h-5 w-5 flex-shrink-0 transform transition-colors duration-150 ease-in-out group-hover:text-gray-400"
                      )}
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                    >
                      <path d="M6 6L14 10L6 14V6Z" fill="currentColor" />
                    </svg>
                  </Disclosure.Button>
                  <Disclosure.Panel className="space-y-1">
                    <NavLink to={`/schema`}>
                      {({ isActive }) => (
                        <div
                          className={classNames(
                            "group flex w-full items-center rounded-md py-2 pl-11 pr-2 text-sm font-medium text-gray-600",
                            isActive
                              ? "bg-gray-300"
                              : "hover:bg-gray-50 hover:text-gray-900"
                          )}
                        >
                          Schema
                        </div>
                      )}
                    </NavLink>
                  </Disclosure.Panel>
                </>
              )}
            </Disclosure>
          </nav>
        </div>
      </div>
    </div>
  );
}
