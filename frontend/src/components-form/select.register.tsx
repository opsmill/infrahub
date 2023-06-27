import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { SelectOption } from "../components/select";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { OpsSelect } from "./select";

type SelectRegisterProps = {
  name: string;
  value: string;
  label: string;
  options: SelectOption[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
};

export const OpsSelectRegister = (props: SelectRegisterProps) => {
  const { name, value, register, setValue, config, options, label, error, isProtected } = props;
  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsSelect
      label={label}
      disabled={false}
      value={value}
      options={options}
      onChange={(item: SelectOption) => setValue(inputRegister.name, item.id)}
      error={error}
      isProtected={isProtected}
    />
  );
};
