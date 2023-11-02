import { Combobox } from "@headlessui/react";
import { CheckIcon } from "@heroicons/react/20/solid";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";
import { Input } from "./input";

export type SelectOption = {
  id: string | number;
  name: string;
};

export enum SelectDirection {
  OVER,
}

type SelectProps = {
  value?: string | number;
  options: SelectOption[];
  onChange: (value: SelectOption) => void;
  disabled?: boolean;
  error?: FormFieldError;
  direction?: SelectDirection;
};

export const Select = (props: SelectProps) => {
  const { options, value, onChange, disabled, error, direction } = props;

  const [query, setQuery] = useState("");

  const [selectedOption, setSelectedOption] = useState<SelectOption | undefined>(
    options.find((option: any) => option?.id === value)
  );

  const filteredOptions =
    query === ""
      ? options
      : options.filter((option: any) =>
          option?.name?.toString().toLowerCase().includes(query.toLowerCase())
        );

  useEffect(() => {
    const currentOption = options.find((option: any) => option?.id === value);

    setSelectedOption(currentOption);
  }, [options.length]);

  return (
    <Combobox
      as="div"
      value={selectedOption}
      onChange={(item) => {
        setQuery("");
        setSelectedOption(item);
        onChange(item);
      }}
      disabled={disabled}>
      <div className="relative mt-1">
        <Combobox.Input
          as={Input}
          value={query ? query : selectedOption?.name ?? ""}
          onChange={(value: any) => {
            // Remove the selected option and update query (allow empty query)
            setSelectedOption(undefined);
            setQuery(value);
          }}
          disabled={disabled}
          error={error}
          className={"pr-8"}
        />
        <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed">
          <ChevronDownIcon className="w-4 h-4 text-gray-400" aria-hidden="true" />
        </Combobox.Button>

        {filteredOptions.length > 0 && (
          <Combobox.Options
            className={classNames(
              "absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-custom-white py-1 text-base shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none sm:text-sm",
              direction === SelectDirection.OVER ? "bottom-0" : ""
            )}>
            {filteredOptions.map((option: any) => (
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
      </div>
    </Combobox>
  );
};
