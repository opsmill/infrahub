import Select, { ActionMeta, MultiValue, StylesConfig } from "react-select";
import makeAnimated from "react-select/animated";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";

const animatedComponents = makeAnimated();

interface Props {
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  onChange: (newValue: MultiValue<SelectOption>, actionMeta: ActionMeta<SelectOption>) => void;
}


const styles: StylesConfig<{ label: string; value: string }, true> = {
  container: (styles) => ({ ...styles, width: "100%" }),
  //   control: (styles) => ({ ...styles }),
  //   option: (styles) => ({ ...styles }),
  //   input: (styles) => ({ ...styles }),
  //   placeholder: (styles) => ({ ...styles }),
  //   singleValue: (styles) => ({ ...styles }),
  //   multiValue: (styles) => ({ ...styles }),
  //   multiValueLabel: (styles) => ({ ...styles }),
  //   multiValueRemove: (styles) => ({ ...styles }),
};

export default function OpsMultiSelect(props: Props) {
  const { value, options, onChange, label } = props;
  // console.log("Selected value: ", value);

  // console.log({
  //   props,
  //   value,
  // });

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900 mt-6">
        {label}
      </label>
      <Select
        value={value}
        options={options}
        onChange={onChange}
        styles={styles}
        isSearchable={false}
        isClearable={false}
        components={animatedComponents}
        isMulti
      />
    </>
  );
}
