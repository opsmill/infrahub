import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { OpsDatePicker } from "./date-picker";
import { useState } from "react";

interface Props {
  name: string;
  label: string;
  value?: Date;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
}

export const OpsDatePickerRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, error } = props;
  const [currentValue, setCurrentValue] = useState(value);

  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsDatePicker
      label={label}
      value={currentValue}
      onChange={(value?: Date) => {
        setCurrentValue(value);
        setValue(inputRegister.name, value);
      }}
      error={error}
    />
  );
};
