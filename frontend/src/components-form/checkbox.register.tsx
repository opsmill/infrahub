import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import OpsCheckox from "./checkbox";

interface Props {
  name: string;
  label: string;
  value: boolean;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  isProtected?: boolean;
}

export const OpsCheckboxRegister = (props: Props) => {
  const { name, value, register, setValue, config, label, isProtected } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsCheckox
      label={label}
      value={value}
      onChange={(value) => {
        setValue(inputRegister.name, value);
      }}
      isProtected={isProtected}
    />
  );
};
