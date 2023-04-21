import { Control, Controller, FieldValues } from "react-hook-form";
import Select, { StylesConfig } from "react-select";
import makeAnimated from "react-select/animated";
import { SelectOption } from "../../components/select";

const animatedComponents = makeAnimated();

interface Props {
  fieldName: string;
  defaultValue: string[]; // List of IDs
  options: SelectOption[];
  onChange: Function;
  control: Control<FieldValues, any>;
}


const styles: StylesConfig<SelectOption, true> = {
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

export default function MultiSelect(props: Props) {
  const { control, fieldName, defaultValue, options } = props;
  const value = options.filter(
    (option) => (defaultValue || []).indexOf(option.id) > -1
  );

  console.log({
    props,
    value,
  });

  return (
    <Controller
      name={fieldName}
      control={control}
      defaultValue={value}
      render={({ field }) => (
        <Select
          value={value}
          styles={styles}
          isSearchable={false}
          isClearable={false}
          components={animatedComponents}
          isMulti
          options={options}
        />
      )}
    />
  );
}
