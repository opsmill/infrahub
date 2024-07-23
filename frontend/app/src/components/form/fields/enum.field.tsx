import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { DynamicEnumFieldProps, FormAttributeValue } from "@/components/form/type";
import { ComboboxProps } from "@/components/ui/combobox";
import { LabelFormField } from "@/components/form/fields/common";
import { Select } from "@/components/inputs/select";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

export interface EnumFieldProps
  extends Omit<DynamicEnumFieldProps, "type">,
    Omit<ComboboxProps, "defaultValue" | "name" | "items"> {}

const EnumField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  items,
  ...props
}: EnumFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="relative flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <Select
                {...field}
                value={fieldData?.value}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
                {...props}
                options={items}
                enum
                className="w-full"
              />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default EnumField;
