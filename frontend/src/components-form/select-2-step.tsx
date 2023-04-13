import { useCallback, useEffect, useState } from "react";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";
import getDropdownOptionsForRelatedPeers from "../utils/dropdownOptionsForRelatedPeers";

export interface iTwoStepDropdownData {
  parent: string;
  child: string;
}

interface Props {
  label: string;
  options: SelectOption[];
  value: iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
}

export const OpsSelect2Step = (props: Props) => {
  const { label, options, value } = props;
  const [optionsRight, setOptionsRight] = useState<SelectOption[]>([]);
  const [selectedLeft, setSelectedLeft] = useState<SelectOption | null>(
    value.parent
      ? options.filter((option) => option.label === value.parent)?.[0]
      : null
  );

  const [selectedRight, setSelectedRight] = useState<SelectOption | null>(
    value.child
      ? optionsRight.filter((option) => option.value === value.child)?.[0]
      : null
  );

  useEffect(() => {
    setSelectedRight(value.child
      ? optionsRight.filter((option) => option.value === value.child)?.[0]
      : null);
  }, [value.child, optionsRight]);

  useEffect(() => {
    if (value) {
      props.onChange(value);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setRightDropdownOptions = useCallback(async () => {
    const objectName = selectedLeft?.value;
    if(objectName) {
      const peerDropdownOptions = await getDropdownOptionsForRelatedPeers([objectName]);
      const options = peerDropdownOptions[objectName];
      setOptionsRight(options.map(option => ({
        label: option.display_label,
        value: option.id,
      })));
    }
  }, [selectedLeft?.value]);

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft, setRightDropdownOptions]);

  return (
    <div className="grid grid-cols-6">
      <div className="sm:col-span-6">
        <label className="block text-sm font-medium leading-6 text-gray-900 capitalize mt-4 mb-2">
          {label}
        </label>
      </div>
      <div className="sm:col-span-3 mr-2">
        <select
          className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          value={selectedLeft ? selectedLeft.value : value.parent}
          placeholder="Choose Type"
          onChange={(e) => {
            setSelectedLeft(
              options.filter((option) => option.value === e.target.value)[0]
            );
            // setSelectedRight(null);
          }}
        >
          {options.map((o, index) => (
            <option key={index} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-3 ml-2">
        {!!selectedLeft && optionsRight.length > 0 && (
          <select
            className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
            placeholder="Choose Item"
            onChange={(e) =>
            {
              const newOption = optionsRight.filter(option => option.value === e.target.value)?.[0];
              setSelectedRight(newOption);
              props.onChange({
                parent: selectedLeft.value,
                child: e.target.value,
              });
            }
            }
            value={selectedRight ? selectedRight.value : value.child}
          >
            <option value=""></option>
            {optionsRight.map((o, index) => (
              <option key={index} value={o.value}>
                {o.label} {o.value.slice(0,5)}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
};
