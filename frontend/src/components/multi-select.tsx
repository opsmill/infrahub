import { Combobox } from "@headlessui/react";
import { CheckIcon } from "@heroicons/react/20/solid";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";
import { MultipleInput } from "./multiple-input";

export type SelectOption = {
  id: string;
  name: string;
};

type SelectProps = {
  value?: SelectOption[];
  options: SelectOption[];
  onChange: (value: SelectOption[]) => void;
  disabled?: boolean;
  error?: FormFieldError;
};

export const MultiSelect = (props: SelectProps) => {
  const { options, value, onChange, disabled, error } = props;

  const [selectedOptions, setSelectedOption] = useState<SelectOption[] | undefined>(value);

  return (
    <Combobox
      as="div"
      value={selectedOptions}
      onChange={(item: SelectOption[]) => {
        setSelectedOption(item);
        onChange(item);
      }}
      disabled={disabled}
      multiple>
      <div className="relative mt-1">
        <Combobox.Input
          className={error ? "ring-red-500 focus:ring-red-600" : ""}
          as={MultipleInput}
          value={selectedOptions}
          onChange={(item: any) => {
            setSelectedOption(item);
            onChange(item);
          }}
        />
        <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed">
          <ChevronDownIcon className="w-4 h-4 text-gray-400" aria-hidden="true" />
        </Combobox.Button>

        {options.length > 0 && (
          <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-custom-white text-base shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none sm:text-sm">
            {options.map((option: any) => (
              <Combobox.Option
                key={option.id}
                value={option}
                className={({ active }) =>
                  classNames(
                    "relative cursor-default select-none py-2 pl-3 pr-9",
                    active ? "bg-custom-blue-600 text-custom-white" : "text-gray-900"
                  )
                }>
                {({ active, selected }) => (
                  <>
                    <span className={classNames("block truncate", selected ? "font-semibold" : "")}>
                      {option.name}
                    </span>

                    {selected && (
                      <span
                        className={classNames(
                          "absolute inset-y-0 right-0 flex items-center pr-4",
                          active ? "text-custom-white" : "text-custom-blue-600"
                        )}>
                        <CheckIcon className="w-4 h-4" aria-hidden="true" />
                      </span>
                    )}
                  </>
                )}
              </Combobox.Option>
            ))}
          </Combobox.Options>
        )}
        {error && error?.message && (
          <div className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2">
            {error?.message}
          </div>
        )}
      </div>
    </Combobox>
  );
};
