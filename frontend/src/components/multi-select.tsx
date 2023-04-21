import { Combobox } from "@headlessui/react";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { classNames } from "../utils/common";
import { MultipleInput } from "./multiple-input";

export type SelectOption = {
  id: string;
  name: string;
}

type SelectProps = {
  value?: SelectOption[];
  options: SelectOption[];
  onChange: (value: SelectOption[]) => void;
  disabled?: boolean;
}

export const MultiSelect = (props: SelectProps) => {
  const { options, value, onChange, disabled } = props;

  const [selectedOptions, setSelectedOption] = useState<SelectOption[] | undefined>(value);

  return (
    <Combobox
      as="div"
      value={selectedOptions}
      onChange={
        (item: SelectOption[]) => {
          console.log("item: ", item);
          setSelectedOption(item);
          onChange(item);
        }
      }
      disabled={disabled}
      multiple
    >
      <div className="relative mt-1">
        <Combobox.Input
          as={MultipleInput}
          value={selectedOptions}
          onChange={
            (item: any) => {
              setSelectedOption(item);
              onChange(item);
            }
          }
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
          options.length > 0
          && (
            <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
              {
                options
                .map(
                  (option: any) => (
                    <Combobox.Option
                      key={option.id}
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
                              )
                            }
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
