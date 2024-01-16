import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import OpsCheckox from "./checkbox";

interface Props {
  name: string;
  label: string;
  value: boolean;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  isProtected?: boolean;
  isOptional?: boolean;
  disabled?: boolean;
  error?: FormFieldError;
}

export const OpsCheckboxRegister = (props: Props) => {
  const { name, register, setValue, config, isProtected, ...propsToPass } = props;

  const inputRegister = register(name, {
    value: props.value ?? "",
    ...config,
  });

  return (
    <OpsCheckox
      {...propsToPass}
      onChange={(value) => {
        setValue(inputRegister.name, value);
      }}
      isProtected={isProtected || props.disabled}
    />
  );
};
