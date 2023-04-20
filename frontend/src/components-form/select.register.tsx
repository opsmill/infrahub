import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { HasNameAndID, OpsSelect } from "./select";

interface Props {
  name: string;
  value: string;
  label: string;
  options: HasNameAndID[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsSelectRegister = (props: Props) => {
  const { name, value, register, setValue, config, options, label } = props;
  const inputRegister = register(
    name,
    {
      value: value ?? "",
      ...config
    }
  );

  return (
    <OpsSelect
      label={label}
      disabled={false}
      value={value}
      options={options}
      onChange={(item) => setValue(inputRegister.name, item)}
    />
  );
};
