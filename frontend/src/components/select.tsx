import { Combobox } from "@headlessui/react";
import { CheckIcon } from "@heroicons/react/20/solid";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useState } from "react";
import { DEFAULT_BRANCH_NAME } from "../config/constants";
import { FormFieldError } from "../screens/edit-form-hook/form";
import ObjectItemCreate from "../screens/object-item-create/object-item-create-paginated";
import { schemaState } from "../state/atoms/schema.atom";
import { schemaKindNameState } from "../state/atoms/schemaKindName.atom";
import { classNames, getTextColor } from "../utils/common";
import { Input } from "./input";
import { MultipleInput } from "./multiple-input";
import SlideOver from "./slide-over";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../state/atoms/branches.atom";

export type SelectOption = {
  id: string | number;
  name: string;
  color?: string; // For dropdown
  description?: string; // For dropdown
};

export enum SelectDirection {
  OVER,
}

type SelectProps = {
  value?: string | number | SelectOption[];
  name: string;
  peer?: string;
  options: SelectOption[];
  onChange: (value: SelectOption | SelectOption[]) => void;
  disabled?: boolean;
  error?: FormFieldError;
  direction?: SelectDirection;
  preventObjectsCreation?: boolean;
  multiple?: boolean;
  dropdown?: boolean;
};

export const Select = (props: SelectProps) => {
  const {
    options,
    value,
    onChange,
    disabled,
    error,
    direction,
    peer,
    preventObjectsCreation,
    multiple,
    ...otherProps
  } = props;

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const branch = useAtomValue(currentBranchAtom);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [localOptions, setLocalOptions] = useState(options);
  const [selectedOption, setSelectedOption] = useState(
    multiple ? value : options?.find((option) => option?.id === value || option.name === value)
  );

  const schemaData = schemaList.find((s) => s.kind === peer);

  const filteredOptions = !query
    ? localOptions
    : localOptions.filter((option) =>
        option?.name?.toString().toLowerCase().includes(query.toLowerCase())
      );

  const addOption = {
    name: "Add option",
    id: "add-new-option",
  };

  const handleChange = (item: any) => {
    if (item.id === addOption.id) {
      setOpen(true);
      return;
    }

    if (multiple) {
      const includesNewItemCreation = item.find((i: any) => i.id === addOption.id);

      if (!includesNewItemCreation) {
        setSelectedOption(item);
        setOpen(false);
        onChange(item);
        return;
      }

      setOpen(true);
      return;
    }

    setSelectedOption(item);
    setQuery("");
    setOpen(false);
    onChange(item);
  };

  const handleCreate = (response: any) => {
    const newItem = {
      id: response.object.id,
      name: response.object.display_label,
    };

    setLocalOptions([...localOptions, newItem]);

    if (multiple && Array.isArray(value)) {
      handleChange([...value, newItem]);

      return;
    }

    handleChange(newItem);
  };

  const handleInputChange = (value: any) => {
    if (multiple) {
      handleChange(value);
      return;
    }

    // Remove the selected option and update query (allow empty query)
    setSelectedOption(undefined);
    setQuery(value);
  };

  const getInputValue = () => {
    if (multiple) {
      return selectedOption;
    }

    if (query) {
      return query;
    }

    if (typeof selectedOption === "object" && !Array.isArray(selectedOption)) {
      return selectedOption?.name;
    }

    return selectedOption;
  };

  const getStyle = () => {
    if (typeof selectedOption === "object" && !Array.isArray(selectedOption)) {
      return {
        backgroundColor: (typeof selectedOption === "object" && selectedOption?.color) || "",
        color:
          typeof selectedOption === "object" && selectedOption?.color
            ? getTextColor(selectedOption?.color)
            : "",
      };
    }

    return {};
  };

  return (
    <>
      <Combobox
        as="div"
        value={selectedOption}
        onChange={handleChange}
        disabled={disabled}
        multiple={multiple}
        {...otherProps}>
        <div className="relative mt-1">
          <Combobox.Input
            as={multiple ? MultipleInput : Input}
            value={getInputValue()}
            onChange={handleInputChange}
            disabled={disabled}
            error={error}
            className={"pr-8"}
            style={getStyle()}
          />
          <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none disabled:cursor-not-allowed">
            <ChevronDownIcon className="w-4 h-4 text-gray-400" aria-hidden="true" />
          </Combobox.Button>

          {filteredOptions && filteredOptions.length > 0 && (
            <Combobox.Options
              className={classNames(
                "absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-custom-white text-base shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none sm:text-sm",
                direction === SelectDirection.OVER ? "bottom-0" : ""
              )}>
              {filteredOptions.map((option) => (
                <Combobox.Option
                  key={option.id}
                  value={option}
                  className={({ active }) =>
                    classNames(
                      "relative cursor-pointer select-none py-2 pl-3 pr-9",
                      active ? "!bg-custom-blue-600" : ""
                    )
                  }
                  style={{
                    backgroundColor: option?.color || "",
                    color: option?.color ? getTextColor(option?.color) : "",
                  }}>
                  {({ active, selected }) => (
                    <>
                      <span
                        className={classNames("block truncate", selected ? "font-semibold" : "")}>
                        {option.name}
                      </span>

                      {option.description && (
                        <span
                          className={classNames(
                            "block truncate italic text-xs",
                            selected ? "font-semibold" : ""
                          )}>
                          {option.description}
                        </span>
                      )}

                      {selected && (
                        <span
                          className={classNames(
                            "absolute inset-y-0 right-0 flex items-center pr-4",
                            active ? "text-custom-white" : "text-custom-blue-600"
                          )}>
                          <CheckIcon className="w-4 h-4" aria-hidden="true" />
                        </span>
                      )}

                      {}
                    </>
                  )}
                </Combobox.Option>
              ))}

              {peer && !preventObjectsCreation && (
                <Combobox.Option
                  value={addOption}
                  className={({ active }) =>
                    classNames(
                      "relative cursor-pointer select-none py-2 pl-3 pr-9 m-2 rounded-md",
                      active ? "bg-custom-blue-600 text-custom-white" : "bg-gray-100 text-gray-900"
                    )
                  }>
                  {({ selected }) => (
                    <span
                      className={classNames(
                        "truncate flex items-center",
                        selected ? "font-semibold" : ""
                      )}>
                      <Icon icon={"mdi:plus"} /> Add {schemaKindName[peer]}
                    </span>
                  )}
                </Combobox.Option>
              )}
            </Combobox.Options>
          )}
        </div>
      </Combobox>

      {peer && !preventObjectsCreation && (
        <SlideOver
          title={
            <div className="space-y-2">
              <div className="flex items-center w-full">
                <span className="text-lg font-semibold mr-3">Create {schemaData?.label}</span>
                <div className="flex-1"></div>
                <div className="flex items-center">
                  <Icon icon={"mdi:layers-triple"} />
                  <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                </div>
              </div>

              <div className="text-sm">{schemaData?.description}</div>

              <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
                <svg
                  className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                  viewBox="0 0 6 6"
                  aria-hidden="true">
                  <circle cx={3} cy={3} r={3} />
                </svg>
                {schemaData?.kind}
              </span>
            </div>
          }
          open={open}
          setOpen={setOpen}
          offset={1}>
          <ObjectItemCreate
            onCreate={handleCreate}
            onCancel={() => setOpen(false)}
            objectname={peer}
            preventObjectsCreation
          />
        </SlideOver>
      )}
    </>
  );
};
