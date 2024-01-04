import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { OpsDatePicker } from "./date-picker";

interface Props {
  name: string;
  label: string;
  value?: Date;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
}

export const OpsDatePickerRegister = (props: Props) => {
  const { name, register, setValue, config, ...propsToPass } = props;

  const inputRegister = register(name, {
    value: props.value || null,
    ...config,
  });

  return (
    <OpsDatePicker
      {...propsToPass}
      onChange={(value?: Date) => setValue(inputRegister.name, value)}
    />
  );
};
