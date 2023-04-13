import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { OpsInput } from "./input";

interface Props {
  name: string;
  label: string;
  value: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsInputRegister = (props: Props) => {
  const { name, value, register, setValue, config, label } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsInput
      label={label}
      value={value}
      onChange={(e) => {
        setValue(inputRegister.name, e.target.value);
      }}
    />
  );
};
