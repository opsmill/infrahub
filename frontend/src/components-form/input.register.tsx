import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { OpsInput } from "./input";
import { FormFieldError } from "../screens/edit-form-hook/form";

interface Props {
  name: string;
  label: string;
  value: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
}

export const OpsInputRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, error } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsInput
      type={config && config.valueAsNumber ? "number" : "text"}
      label={label}
      value={value}
      onChange={(value) => setValue(inputRegister.name, value)}
      error={error}
    />
  );
};
