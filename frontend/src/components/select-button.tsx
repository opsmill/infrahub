import { Listbox, Transition } from "@headlessui/react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { Fragment } from "react";
import { classNames } from "../utils/common";

// type SelectButtonProps = {};

export const SelectButton = (props: any) => {
  const {
    label,
    value,
    valueLabel,
    onChange,
    options,
    renderOption
  } = props;

  return (
    <Listbox
      value={value}
      onChange={onChange}
    >
      {
        ({ open }) => (
          <>
            <Listbox.Label className="sr-only">{label}</Listbox.Label>
            <div className="relative">
              <div className="inline-flex divide-x divide-blue-600 rounded-md shadow-sm">
                <div className="inline-flex divide-x divide-blue-600 rounded-md shadow-sm">
                  <div className="inline-flex items-center rounded-l-md border border-transparent bg-blue-500 py-2 pl-3 pr-4 text-white shadow-sm">
                    {valueLabel}
                  </div>
                  <Listbox.Button className="inline-flex items-center rounded-l-none rounded-r-md bg-blue-500 p-2 text-sm font-medium text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-50">
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
                  {
                    options
                    .map(
                      (option: any) => (
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
                          {(attributes) => renderOption({ option, ...attributes })}
                        </Listbox.Option>
                      )
                    )
                  }
                </Listbox.Options>
              </Transition>
            </div>
          </>
        )
      }
    </Listbox>
  );
};
