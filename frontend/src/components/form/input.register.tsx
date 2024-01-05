import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { OpsInput } from "./input";

interface Props {
  inputType: string;
  name: string;
  label: string;
  value: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  disabled?: boolean;
}

export const OpsInputRegister = (props: Props) => {
  const { name, register, setValue, config, inputType, ...propsToPass } = props;

  const inputRegister = register(name, {
    value: props.value || "",
    ...config,
  });

  return (
    <OpsInput
      {...propsToPass}
      type={inputType}
      onChange={(value) => setValue(inputRegister.name, value)}
    />
  );
};
