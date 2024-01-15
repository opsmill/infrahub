import { useState } from "react";
import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { SelectOption } from "../inputs/select";
import OpsList from "./list";

interface Props {
  name: string;
  label: string;
  value: (string | SelectOption)[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
  disabled?: boolean;
}

export const OpsListRegister = (props: Props) => {
  const { name, value, register, setValue, config, isProtected, ...propsToPass } = props;

  const multiSelectRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  const [selectedOptions, setSelectedOptions] = useState(value);

  return (
    <OpsList
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
