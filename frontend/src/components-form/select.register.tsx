import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { HasNameAndID, OpsSelect } from "./select";

interface Props {
  name: string;
  value: string;
  options: HasNameAndID[];
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsSelectRegister = (props: Props) => {
  const { name, value, register, setValue, config, options } = props;
  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsSelect
      disabled={false}
      value={value}
      options={options}
      onChange={(item) => {
        console.log("Changed to: ", item);
        setValue(inputRegister.name, item.id);
      }}
    />
  );
};
