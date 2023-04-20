import { useCallback, useEffect, useState } from "react";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";
import getDropdownOptionsForRelatedPeers from "../utils/dropdownOptionsForRelatedPeers";
import { OpsSelect } from "./select";

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
        <label className="block text-sm font-medium leading-6 text-gray-900 capitalize">
          {label}
        </label>
      </div>
      <div className="sm:col-span-3 mr-2 mt-1">
        <OpsSelect disabled={false} value={selectedLeft ? selectedLeft.value : value.parent} options={options.map(o => ({
          name: o.label,
          id: o.value,
        }))} label="" onChange={(e) => {
          setSelectedLeft(
            options.filter((option) => option.value === e.id)[0]
          );
          // setSelectedRight(null);
        }} />
      </div>
      <div className="sm:col-span-3 ml-2 mt-1">
        {!!selectedLeft && optionsRight.length > 0 && (
          <OpsSelect disabled={false} value={selectedRight ? selectedRight.value : value.child} options={optionsRight.map(o => ({
            name: o.label,
            id: o.value,
          }))} label=""
          onChange={(e) =>
          {
            const newOption = optionsRight.filter(option => option.value === e.id)?.[0];
            setSelectedRight(newOption);
            props.onChange({
              parent: selectedLeft.value,
              child: e.id,
            });
          }
          } />
        )}
      </div>
    </div>
  );
};
