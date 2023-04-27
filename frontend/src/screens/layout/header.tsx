import { Menu, Transition } from "@headlessui/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import {
  Bars3BottomLeftIcon,
  BellIcon,
  ClockIcon
} from "@heroicons/react/24/outline";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { Fragment, useEffect, useState } from "react";
import Datetime from "react-datetime";
import "react-datetime/css/react-datetime.css";
import { StringParam, useQueryParam } from "use-query-params";

import BranchSelector from "../../components/branch-selector";
import { CONFIG } from "../../config/config";
import { QSP } from "../../config/qsp";
import { graphQLClient } from "../../graphql/graphqlClient";
import { timeState } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { userNavigation } from "./navigation-list";

interface Props {
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

export default function Header(props: Props) {
  const [date, setDate] = useAtom(timeState);
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, StringParam);
  const [isDateDefault, setIsDateDefault] = useState(qspDate ? false : true);
  const { setSidebarOpen } = props;

  useEffect(() => {
    if(date !== undefined) {
      graphQLClient.setEndpoint(CONFIG.GRAPHQL_URL(undefined, date));
    }
  }, [date]);

  return (
    <div className="z-10 flex h-16 flex-shrink-0 bg-white shadow">
      <button
        type="button"
        className="border-r border-gray-200 px-4 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 md:hidden"
        onClick={() => setSidebarOpen(true)}
      >
        <span className="sr-only">Open sidebar</span>
        <Bars3BottomLeftIcon className="h-6 w-6" aria-hidden="true" />
      </button>
      <div className="flex flex-1 justify-between px-4">
        <div className="flex flex-1 opacity-30">
          <form className="flex w-full md:ml-0" action="#" method="GET">
            <label htmlFor="search-field" className="sr-only">
              Search
            </label>
            <div className="relative w-full text-gray-400 focus-within:text-gray-600">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center">
                <MagnifyingGlassIcon className="h-5 w-5" aria-hidden="true" />
              </div>
              <input
                onChange={() => {}}
                id="search-field"
                className="block h-full w-full border-transparent py-2 pl-8 pr-3 text-gray-900 placeholder-gray-500 focus:border-transparent focus:placeholder-gray-400 focus:outline-none focus:ring-0 sm:text-sm cursor-not-allowed"
                placeholder="Search"
                type="search"
                name="search"
              />
            </div>
          </form>
        </div>
        <div className="ml-4 flex items-center md:ml-6">
          {isDateDefault && (
            <button
              onClick={() => {
                setIsDateDefault(false);
                setDate(null);
              }}
              type="button"
              className="mr-3 rounded-full bg-white p-1 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              <span className="sr-only">Query Date Time</span>
              <ClockIcon className="h-6 w-6" aria-hidden="true" />
            </button>
          )}

          {!isDateDefault && (
            <Datetime
              initialValue={qspDate ? new Date(qspDate) : date}
              onChange={(a: any) => {
                if (a.toDate) {
                  setDate(a.toDate());
                  setQspDate(formatISO(a.toDate()));
                } else {
                  // undefined is needed to remove a parameter from the QSP
                  setQspDate(undefined);
                }
              }}
              className="mr-5"
              inputProps={{
                className:
                  "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
              }}
              renderView={(mode: any, renderDefault: any) => {
                // Only for years, months and days view
                if (mode === "time") return renderDefault();

                return (
                  <div className="wrapper">
                    {renderDefault()}
                    <div className="controls">
                      <button onClick={() => {
                        setIsDateDefault(true);
                        setDate(null);
                        // undefined is needed to remove a parameter from the QSP
                        setQspDate(undefined);
                      }}>
                        Now
                      </button>
                    </div>
                  </div>
                );
              }}
            />
          )}

          <BranchSelector />
          <button
            type="button"
            className="ml-3 rounded-full bg-white p-1 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 opacity-30 cursor-not-allowed"
          >
            <span className="sr-only">View notifications</span>
            <BellIcon className="h-6 w-6" aria-hidden="true" />
          </button>

          {/* Profile dropdown */}
          <Menu as="div" className="relative ml-3">
            <div>
              <Menu.Button className="flex max-w-xs items-center rounded-full bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 opacity-30">
                <span className="sr-only">Open user menu</span>
                <img
                  className="h-10 w-10 rounded-full object-cover cursor-not-allowed"
                  src="https://shotkit.com/wp-content/uploads/2020/07/headshots_image002.jpg"
                  alt=""
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
              <Menu.Items className="absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none opacity-30">
                {userNavigation.map((item) => (
                  <Menu.Item key={item.name}>
                    {({ active }) => (
                      <a
                        href={item.href}
                        className={classNames(
                          active ? "bg-gray-100" : "",
                          "block px-4 py-2 text-sm text-gray-700"
                        )}
                      >
                        {item.name}
                      </a>
                    )}
                  </Menu.Item>
                ))}
              </Menu.Items>
            </Transition>
          </Menu>
        </div>
      </div>
    </div>
  );
}
