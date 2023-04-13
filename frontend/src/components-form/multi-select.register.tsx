import { useState } from "react";
import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";
import OpsMultiSelect from "./multi-select";

interface Props {
  name: string;
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsMultiSelectRegister = (props: Props) => {
  const { name, value, register, setValue, config, options, label } = props;
  const multiSelectRegister = register(name, {
    value: value ?? "",
    ...config
  });

  const [selectedOptions, setSelectedOptions] = useState<SelectOption[]>(value);

  return (
    <OpsMultiSelect label={label} options={options} value={selectedOptions} onChange={(newValue) => {
      setSelectedOptions(newValue as SelectOption[]);
      setValue(multiSelectRegister.name, newValue);
    }} />
  );
};
