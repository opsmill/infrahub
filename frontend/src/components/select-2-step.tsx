import { useEffect, useState } from "react";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";

export interface iTwoStepSelectOption extends SelectOption {
    options: SelectOption[];
}

export interface iTwoStepDropdownData {
    parent: string;
    child: string;
}

interface Props {
    options: iTwoStepSelectOption[];
    label: string;
    defaultValue: iTwoStepDropdownData;
    onChange: (value: iTwoStepDropdownData) => void;
}

export const Select2Step = (props: Props) => {
  const {label, options, defaultValue} = props;
  const [selected, setSelected] = useState<iTwoStepSelectOption | null>(defaultValue.parent ? options.filter(option => option.value === defaultValue.parent)[0] : null);

  useEffect(() => {
    if(defaultValue) {
      props.onChange(defaultValue);
    }
  });

  return (
    <div className="grid grid-cols-7">
      <div className="sm:col-span-1"></div>
      <div className="sm:col-span-6">
        <label
          className="block text-sm font-medium leading-6 text-gray-900 capitalize mt-4 mb-2">
          {label}
        </label>
      </div>
      <div className="sm:col-span-1"></div>
      <div className="sm:col-span-3 mr-2">
        <select
          className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          defaultValue={defaultValue.parent}
          placeholder="Choose Type"
          onChange={(e) => setSelected(options.filter(option => option.value === e.target.value)[0])}
        >
          {options.map((o, index) => (
            <option key={index} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-3 ml-2">
        {!!selected && <select
          className="block w-full rounded-md border-0 py-1.5 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600 sm:text-sm sm:leading-6"
          defaultValue={defaultValue.child}
          placeholder="Choose Item"
          onChange={(e) => props.onChange({ parent: selected.value, child: e.target.value})}
        //   {...register(name, {
        //     value: metaFieldObject ? metaFieldObject.id : "",
        //   })}
        >
          {selected.options.map((o, index) => (
            <option key={index} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>}
      </div>
    </div>
  );
};