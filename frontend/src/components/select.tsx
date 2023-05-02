import { Combobox } from "@headlessui/react";
import { CheckIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { classNames } from "../utils/common";
import { Input } from "./input";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { ChevronDownIcon } from "@heroicons/react/24/outline";

export type SelectOption = {
  id: string;
  name: string;
}

type SelectProps = {
  value?: string;
  options: SelectOption[];
  onChange: (value: SelectOption) => void;
  disabled?: boolean;
  error?: FormFieldError;
}

export const Select = (props: SelectProps) => {
  const { options, value, onChange, disabled, error } = props;

  const [query, setQuery] = useState("");

  const [selectedOption, setSelectedOption] = useState<SelectOption | undefined>(options.find((option: any) => option?.id === value));

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
      value={selectedOption}
      onChange={
        (item) => {
          setQuery("");
          setSelectedOption(item);
          onChange(item);
        }
      }
      disabled={disabled}
    >
      <div className="relative mt-1">
        <Combobox.Input
          as={Input}
          value={query ? query : selectedOption?.name ?? ""}
          onChange={
            (value: any) => {
              // Remove the selected option and update query (allow empty query)
              setSelectedOption(undefined);
              setQuery(value);
            }
          }
          disabled={disabled}
          error={error}
        />
        <Combobox.Button
          className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed"
        >
          <ChevronDownIcon
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
