import { Fragment } from "react";
import { Listbox, Transition } from "@headlessui/react";
import { CheckIcon, ChevronDownIcon } from "@heroicons/react/20/solid";
import { classNames } from "../../App";
import { CircleStackIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { branchState } from "../../state/atoms/branch.atom";
import { useAtom } from "jotai";
import { graphQLClient } from "../..";
import { CONFIG } from "../../config/config";

const branches = [
  {
    name: "main",
    description: "Default Branch",
    is_default: true,
    origin_branch: "main",
    branched_from: "2023-02-15T11:36:18.476325Z",
    timeSince: "3 days ago",
    is_data_only: false,
    current: true,
  },
  {
    name: "cr1245",
    description: "Default Branch",
    is_default: false,
    origin_branch: "main",
    branched_from: "2023-02-15T11:36:18.476325Z",
    timeSince: "5 hours ago",
    is_data_only: true,
    current: false,
  },
  {
    name: "cr1248",
    description: "Default Branch",
    is_default: false,
    origin_branch: "main",
    branched_from: "2023-02-15T11:36:18.476325Z",
    timeSince: "10 mins ago",
    is_data_only: false,
    current: false,
  },
];

export default function BranchSelector() {
  const [selected, setSelected] = useAtom(branchState);

  return (
    <Listbox
      value={selected}
      onChange={(value) => {
        graphQLClient.setEndpoint(CONFIG.BACKEND_URL(value.name));
        setSelected(value);
      }}
    >
      {({ open }) => (
        <>
          <Listbox.Label className="sr-only"> Change branch </Listbox.Label>
          <div className="relative">
            <div className="inline-flex divide-x divide-blue-600 rounded-md shadow-sm">
              <div className="inline-flex divide-x divide-blue-600 rounded-md shadow-sm">
                <div className="inline-flex items-center rounded-l-md border border-transparent bg-blue-500 py-2 pl-3 pr-4 text-white shadow-sm">
                  <CheckIcon className="h-5 w-5" aria-hidden="true" />
                  <p className="ml-2.5 text-sm font-medium">{selected.name}</p>
                </div>
                <Listbox.Button className="inline-flex items-center rounded-l-none rounded-r-md bg-blue-500 p-2 text-sm font-medium text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-50">
                  <span className="sr-only">Change published status</span>
                  <ChevronDownIcon
                    className="h-5 w-5 text-white"
                    aria-hidden="true"
                  />
                </Listbox.Button>
              </div>
            </div>

            <Transition
              show={open}
              as={Fragment}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <Listbox.Options className="absolute right-0 z-20 mt-2 w-72 origin-top-right divide-y divide-gray-200 overflow-hidden rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                {branches.map((option) => (
                  <Listbox.Option
                    key={option.name}
                    className={({ active }) =>
                      classNames(
                        active ? "text-white bg-blue-500" : "text-gray-900",
                        "cursor-default select-none p-4 text-sm"
                      )
                    }
                    value={option}
                  >
                    {({ selected, active }) => (
                      <div className="flex relative flex-col">
                        {option.is_data_only && (
                          <div className="absolute bottom-0 right-0">
                            <CircleStackIcon
                              className={classNames(
                                "h-4 w-4",
                                active ? "text-white" : "text-gray-500"
                              )}
                            />
                          </div>
                        )}

                        {option.is_default && (
                          <div className="absolute bottom-0 right-0">
                            <ShieldCheckIcon
                              className={classNames(
                                "h-4 w-4",
                                active ? "text-white" : "text-gray-500"
                              )}
                            />
                          </div>
                        )}

                        <div className="flex justify-between">
                          <p
                            className={
                              selected ? "font-semibold" : "font-normal"
                            }
                          >
                            {option.name}
                          </p>
                          {selected ? (
                            <span
                              className={
                                active ? "text-white" : "text-blue-500"
                              }
                            >
                              <CheckIcon
                                className="h-5 w-5"
                                aria-hidden="true"
                              />
                            </span>
                          ) : null}
                        </div>
                        <p
                          className={classNames(
                            active ? "text-blue-200" : "text-gray-500",
                            "mt-2"
                          )}
                        >
                          {option.timeSince}
                        </p>
                      </div>
                    )}
                  </Listbox.Option>
                ))}
              </Listbox.Options>
            </Transition>
          </div>
        </>
      )}
    </Listbox>
  );
}
