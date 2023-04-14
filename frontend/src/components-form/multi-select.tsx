import { ChevronUpDownIcon } from "@heroicons/react/24/outline";
import Select, { ActionMeta, MultiValue, StylesConfig } from "react-select";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";

// const animatedComponents = makeAnimated();

interface Props {
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  onChange: (newValue: MultiValue<SelectOption>, actionMeta: ActionMeta<SelectOption>) => void;
}


const styles: StylesConfig<{ label: string; value: string }, true> = {
  container: (styles) => ({ ...styles, width: "100%", borderRadius: 20 }),
  control: (styles) => ({ ...styles, borderRadius: 6, borderColor: "rgba(107, 114, 128, 0.25)" }),
  //   option: (styles) => ({ ...styles }),
  //   input: (styles) => ({ ...styles }),
  //   placeholder: (styles) => ({ ...styles }),
  //   singleValue: (styles) => ({ ...styles }),
  multiValue: (styles) => ({ ...styles, borderRadius: 4 }),
  //   multiValueLabel: (styles) => ({ ...styles }),
  //   multiValueRemove: (styles) => ({ ...styles }),
};

const DropdownIndicator = (props: any) => {
  return (
    <div>
      <ChevronUpDownIcon className="h-5 w-5 text-gray-400 mx-2 cursor-pointer" aria-hidden="true"></ChevronUpDownIcon>
    </div>
  );
};

const IndicatorSeparator = () => null;

export default function OpsMultiSelect(props: Props) {
  const { value, options, onChange, label } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <Select
        value={value}
        options={options}
        onChange={onChange}
        styles={styles}
        isSearchable={false}
        isClearable={false}
        placeholder=""
        components={{ DropdownIndicator, IndicatorSeparator }}
        isMulti
      />
    </>
  );
}
