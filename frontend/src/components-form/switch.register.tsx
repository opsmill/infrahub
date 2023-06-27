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
  onChange?: Function;
  error?: FormFieldError;
  isProtected?: boolean;
}

export const OpsSwitchRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, onChange, error, isProtected } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsSwitch
      error={error}
      label={label}
      value={value}
      onChange={(value) => {
        if (onChange) {
          onChange(value);
        }
        setValue(inputRegister.name, value);
      }}
      isProtected={isProtected}
    />
  );
};
