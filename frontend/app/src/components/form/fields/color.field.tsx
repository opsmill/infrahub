import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps, FormAttributeValue } from "@/components/form/type";
import { InputProps } from "@/components/ui/input";
import { ColorPicker } from "@/components/inputs/color-picker";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const ColorField = ({
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
              <ColorPicker
                {...field}
                value={fieldData?.value}
                onChange={(newValue: string) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
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

export default ColorField;
