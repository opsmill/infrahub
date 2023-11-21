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
  isOptional?: boolean;
  disabled?: boolean;
}

export const OpsSwitchRegister = (props: Props) => {
  const { name, register, setValue, config, onChange, isProtected, ...propsToPass } = props;

  const inputRegister = register(name, {
    value: props.value ?? "",
    ...config,
  });

  return (
    <OpsSwitch
      {...propsToPass}
      onChange={(value) => {
        if (onChange) {
          onChange(value);
        }
        setValue(inputRegister.name, value);
      }}
      isProtected={isProtected || props.disabled}
    />
  );
};
