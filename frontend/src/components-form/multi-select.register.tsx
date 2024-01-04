import { useState } from "react";
import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { SelectOption } from "../components/inputs/select";
import { FormFieldError } from "../screens/edit-form-hook/form";
import OpsMultiSelect from "./multi-select";

interface Props {
  name: string;
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
  disabled?: boolean;
}

export const OpsMultiSelectRegister = (props: Props) => {
  const { name, value, register, setValue, config, isProtected, ...propsToPass } = props;

  const multiSelectRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  const [selectedOptions, setSelectedOptions] = useState<SelectOption[]>(value);

  return (
    <OpsMultiSelect
      {...propsToPass}
      value={selectedOptions}
      onChange={(newValue) => {
        setSelectedOptions(newValue as SelectOption[]);
        setValue(multiSelectRegister.name, newValue);
      }}
      isProtected={isProtected || props.disabled}
    />
  );
};
