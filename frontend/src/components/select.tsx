import { Combobox } from "@headlessui/react";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { classNames } from "../utils/common";
import { Input } from "./input";

// type Option = {} // Object with name property

// type SelectProps = {
//   value: string
// }

// interface SelectProps {
//   value: string
// }

export const Select = (props: any) => {
  const { options, value, onChange, disabled } = props;

  const [query, setQuery] = useState("");

  const filteredOptions =
    query === ""
      ? options
      : options
      .filter(
        (option: any) => option?.name.toLowerCase().includes(query.toLowerCase())
      );

  return (
    <Combobox
      as="div"
      value={value}
      onChange={onChange}
      disabled={disabled}
    >
      <div className="relative mt-1">
        <Combobox.Input
          as={Input}
          value={value}
          onChange={(event) => setQuery(event.target.value)}
          disabled={disabled}
        />
        <Combobox.Button
          className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed"
        >
          <ChevronUpDownIcon
            className="h-5 w-5 text-gray-400"
            aria-hidden="true"
          />
        </Combobox.Button>

        {
          filteredOptions.length > 0
          && (
            <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
              {
                filteredOptions
                .map(
                  (option: any) => (
                    <Combobox.Option
                      key={option}
                      value={option}
                      className={({ active }) =>
                        classNames(
                          "relative cursor-default select-none py-2 pl-3 pr-9",
                          active ? "bg-indigo-600 text-white" : "text-gray-900"
                        )
                      }
                    >
                      {
                        ({ active, selected }) => (
                          <>
                            <span
                              className={classNames(
                                "block truncate",
                                selected ? "font-semibold" : ""
                              )}
                            >
                              {option.name}
                            </span>

                            {
                              selected
                              && (
                                <span
                                  className={classNames(
                                    "absolute inset-y-0 right-0 flex items-center pr-4",
                                    active ? "text-white" : "text-indigo-600"
                                  )}
                                >
                                  <CheckIcon className="h-5 w-5" aria-hidden="true" />
                                </span>
                              )}
                          </>
                        )
                      }
                    </Combobox.Option>
                  )
                )
              }
            </Combobox.Options>
          )
        }
      </div>
    </Combobox>
  );
};
