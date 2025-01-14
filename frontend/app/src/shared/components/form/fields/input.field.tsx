import { LabelFormField } from "@/shared/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, InputProps } from "@/shared/components/ui/input";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const InputField = ({
  defaultValue = { source: null, value: null },
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
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <Input
                {...field}
                value={(fieldData?.value as string) ?? ""}
                onChange={(event) => {
                  field.onChange(updateFormFieldValue(event.target.value, defaultValue));
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
