import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../screens/edit-form-hook/form";
import OpsSwitch from "./switch";

interface Props {
  name: string;
  label: string;
  value: boolean;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
}

export const OpsSwitchRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, error } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsSwitch
      error={error}
      label={label}
      value={value}
      onChange={(value) => {
        setValue(inputRegister.name, value);
      }}
    />
  );
};
