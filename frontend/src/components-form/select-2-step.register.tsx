import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { SelectOption } from "../screens/edit-form-hook/dynamic-control-types";
import { OpsSelect2Step, iTwoStepDropdownData } from "./select-2-step";

interface Props {
  label: string;
  options: SelectOption[];
  value: iTwoStepDropdownData;
  name: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
}

export const OpsSelect2StepRegister = (props: Props) => {
  const { name, value, register, setValue, config, options, label } = props;
  const inputRegister = register(name, {
    value: value ?? "",
    ...config
  });

  return (
    <OpsSelect2Step
      label={label}
      value={value}
      options={options}
      onChange={(option) => {
        setValue(inputRegister.name, option.child);
      }}
    />
  );
};
