import { useState } from "react";
import { FieldValues, RegisterOptions, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { OpsCodeEditor } from "./code-editor";

interface Props {
  name: string;
  label: string;
  value?: string;
  register: UseFormRegister<FieldValues>;
  config?: RegisterOptions<FieldValues, string> | undefined;
  setValue: UseFormSetValue<FieldValues>;
  error?: FormFieldError;
}

export const CodeEditorRegister = (props: Props) => {
  const { name, value, register, setValue, config, ...propsToPass } = props;
  const [currentValue, setCurrentValue] = useState(value ? JSON.stringify(value) : null);

  const inputRegister = register(name, {
    value: value ?? "",
    ...config,
  });

  return (
    <OpsCodeEditor
      {...propsToPass}
      value={currentValue}
      onChange={(value: string) => {
        // Set the JSON as string in state
        setCurrentValue(value);

        try {
          // Store the value as JSON
          const newValue = JSON.parse(value ?? "");
          setValue(inputRegister.name, newValue);
        } catch (e) {
          console.log("e: ", e);
        }
      }}
    />
  );
};
