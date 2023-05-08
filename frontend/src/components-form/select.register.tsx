import {
  FieldValues,
  RegisterOptions,
  UseFormRegister,
  UseFormSetValue,
} from "react-hook-form";
import { OpsSelect } from "./select";
import { SelectOption } from "../components/select";
import { FormFieldError } from "../screens/edit-form-hook/form";

type SelectRegisterProps = {
  name: string;
  value: string;
  label: string;
  options: SelectOption[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
};

export const OpsSelectRegister = (props: SelectRegisterProps) => {
  const { name, value, register, setValue, config, options, label, error } =
    props;
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
    />
  );
};
