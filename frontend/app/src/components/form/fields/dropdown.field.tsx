import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Select, SelectProps } from "@/components/inputs/select";
import { DynamicDropdownFieldProps, FormAttributeValue } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

export interface DropdownFieldProps
  extends Omit<DynamicDropdownFieldProps, "type">,
    Omit<SelectProps, "defaultValue" | "name" | "options"> {}

const DropdownField = ({
  defaultValue,
  description,
  items,
  label,
  name,
  rules,
  unique,
  ...props
}: DropdownFieldProps) => {
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
              fieldData={fieldData}
            />

            <FormInput>
              <Select
                {...field}
                value={fieldData?.value}
                {...props}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
                options={items}
                dropdown
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

export default DropdownField;
