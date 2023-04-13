import { Combobox } from "@headlessui/react";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { classNames } from "../utils/common";

export type HasNameAndID = {
  id: string;
  name: string;
}

interface Props {
  value: string | undefined;
  options: Array<HasNameAndID>;
  disabled: boolean;
  onChange: (value: HasNameAndID) => void;
}

export const OpsSelect = (props: Props) => {
  const { disabled, options, onChange, value } = props;
  const [query, setQuery] = useState("");
  const [selectedOption, setSelectedOption] = useState<HasNameAndID>(options.filter(option => option?.id === value)[0]);

  const filteredOptions =
    query === ""
      ? options
      : options.filter((option) => {
        return option.name.toLowerCase().includes(query.toLowerCase());
      });

  return (
    <Combobox disabled={disabled} as="div" value={selectedOption} onChange={(item: HasNameAndID) => {
      setSelectedOption(item);
      onChange(item);
    }}>
      <Combobox.Label className="block text-sm font-medium leading-6 text-gray-900">Assigned to</Combobox.Label>
      <div className="relative mt-2">
        <Combobox.Input
          disabled={disabled}
          className="w-full rounded-md border-0 bg-white py-1.5 pl-3 pr-10 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
          onChange={(event) => setQuery(event.target.value)}
          displayValue={(selected: HasNameAndID | undefined) => selected?.name ?? ""}
        />
        <Combobox.Button disabled={disabled} className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none">
          <ChevronUpDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
        </Combobox.Button>

        {filteredOptions.length > 0 && (
          <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
            {filteredOptions.map((option) => (
              <Combobox.Option
                key={option.name}
                value={option}
                className={({ active }) =>
                  classNames(
                    "relative cursor-default select-none py-2 pl-3 pr-9",
                    active ? "bg-indigo-600 text-white" : "text-gray-900"
                  )
                }
              >
                {({ active, selected }) => (
                  <>
                    <span className={classNames("block truncate", selected ? "font-semibold" : "")}>{option.name}</span>

                    {selected && (
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
                )}
              </Combobox.Option>
            ))}
          </Combobox.Options>
        )}
      </div>
    </Combobox>
  );
};