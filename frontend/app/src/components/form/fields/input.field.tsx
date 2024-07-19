import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Input, InputProps } from "@/components/ui/input";
import { FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const InputField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: InputFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData = field.value;

        return (
          <div className="relative mb-2 flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <Input
                {...field}
                {...field}
                value={fieldData?.value ?? ""}
                onChange={(event) => {
                  field.onChange(
                    updateFormFieldValue(
                      props.type === "number" ? event.target.valueAsNumber : event.target.value,
                      defaultValue
                    )
                  );
                }}
                {...props}
              />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default InputField;
