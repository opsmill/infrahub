import { useCallback, useEffect, useState } from "react";
import getDropdownOptionsForRelatedPeers from "../utils/dropdownOptionsForRelatedPeers";
import { SelectOption } from "./select";

export interface iTwoStepDropdownData {
  parent: string;
  child: string;
}

interface Props {
  label: string;
  optionsLeft: SelectOption[];
  defaultValue: iTwoStepDropdownData;
  onChange: (value: iTwoStepDropdownData) => void;
}

export const Select2Step = (props: Props) => {
  const { label, optionsLeft, defaultValue } = props;
  const [optionsRight, setOptionsRight] = useState<SelectOption[]>([]);
  const [selectedLeft, setSelectedLeft] = useState<SelectOption | null>(
    defaultValue.parent
      ? optionsLeft.filter((option) => option.name === defaultValue.parent)?.[0]
      : null
  );
  const [selectedRight, setSelectedRight] = useState<SelectOption | null>(
    defaultValue.child
      ? optionsRight.filter((option) => option.name === defaultValue.child)?.[0]
      : null
  );

  useEffect(() => {
    if (defaultValue) {
      props.onChange(defaultValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setRightDropdownOptions = useCallback(
    async () => {
      const objectName = selectedLeft?.id;

      if(objectName) {
        const peerDropdownOptions = await getDropdownOptionsForRelatedPeers([objectName]);

        const options = peerDropdownOptions[objectName];

        setOptionsRight(
          options
          .map(
            option => ({
              name: option.display_label,
              id: option.id,
            })
          )
        );
      }
    },
    [selectedLeft?.id]
  );

  useEffect(() => {
    setRightDropdownOptions();
  }, [selectedLeft, setRightDropdownOptions]);

  return (
    <div className="grid grid-cols-7">
      <div className="sm:col-span-1"></div>
      <div className="sm:col-span-6">
        <label className="block text-sm font-medium leading-6 text-gray-900 capitalize mt-4 mb-2">
          {label}
        </label>
      </div>
      <div className="sm:col-span-1"></div>
      <div className="sm:col-span-3 mr-2">
        <select
          className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          defaultValue={defaultValue.parent}
          placeholder="Choose Type"
          onChange={(e) => {
            setSelectedLeft(
              optionsLeft.filter((option) => option.id === e.target.value)[0]
            );
            // setSelectedRight(null);
          }}
        >
          {optionsLeft.map((o, index) => (
            <option key={index} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-3 ml-2">
        {
          !!selectedLeft
          && optionsRight.length
          && (
            <select
              className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
              placeholder="Choose Item"
              onChange={
                (e) =>
                {
                  setSelectedRight(optionsRight.filter(option => option.id === e.target.value)?.[0]);
                  props.onChange({
                    parent: selectedLeft.id,
                    child: e.target.value,
                  });
                }
              }
              value={selectedRight ? selectedRight.id : defaultValue ? defaultValue.child : ""}
            >
              <option value=""></option>
              {optionsRight.map((o, index) => (
                <option key={index} value={o.id}>
                  {o.name} {o.id.slice(0,5)}
                </option>
              ))}
            </select>
          )
        }
      </div>
    </div>
  );
};
