import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import OpsSwitch from "./switch";

interface Props {
  name: string;
  label: string;
  value: boolean;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsSwitchRegister = (props: Props) => {
  const { name, value, register, setValue, config, label } = props;

  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsSwitch
      label={label}
      value={value}
      onChange={(value) => {
        setValue(inputRegister.name, value);
      }}
    />
  );
};
