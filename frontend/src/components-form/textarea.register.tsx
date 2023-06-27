import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { OpsTextarea } from "./textarea";

interface Props {
  name: string;
  label: string;
  value: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
}

export const OpsTextareaRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, error, isProtected } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsTextarea
      label={label}
      value={value}
      onChange={(value) => setValue(inputRegister.name, value)}
      error={error}
      isProtected={isProtected}
    />
  );
};
