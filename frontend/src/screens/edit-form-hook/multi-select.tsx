import { Controller, Control, FieldValues } from "react-hook-form";
import Select, { StylesConfig } from "react-select";
import makeAnimated from "react-select/animated";

const animatedComponents = makeAnimated();

interface Props {
  fieldName: string;
  defaultValue: string[];
  options: { label: string; value: string }[];
  onChange: Function;
  control: Control<FieldValues, any>;
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

export default function MultiSelect(props: Props) {
  const { control, fieldName, defaultValue, options } = props;
  const def = options.filter(
    (option) => (defaultValue || []).indexOf(option.value) > -1
  );

  return (
    <Controller
      name={fieldName}
      control={control}
      defaultValue={def}
      render={({ field }) => (
        <Select
          styles={styles}
          isSearchable={false}
          isClearable={false}
          components={animatedComponents}
          {...field}
          isMulti
          options={options}
        />
      )}
    />
  );
}
