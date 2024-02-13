import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { SelectOption } from "../inputs/select";
import { OpsSelect2Step, iTwoStepDropdownData } from "./select-2-step";

interface Props {
  label: string;
  options: SelectOption[];
  value: string | iTwoStepDropdownData;
  name: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  disabled?: boolean;
}

export const OpsSelect2StepRegister = (props: Props) => {
  const { name, register, setValue, config, isProtected, disabled, ...propsToPass } = props;

  const inputRegister = register(name, {
    value: props.value ?? "",
    ...config,
  });

  return (
    <OpsSelect2Step
      {...propsToPass}
      onChange={(option) => {
        setValue(inputRegister.name, option.child);
      }}
      isProtected={isProtected || disabled}
    />
  );
};
