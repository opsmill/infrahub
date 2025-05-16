import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { DynamicDropdownFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Dropdown, DropdownProps } from "@/shared/components/inputs/dropdown";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface DropdownFieldProps
  extends Omit<DynamicDropdownFieldProps, "type">,
    Omit<DropdownProps, "defaultValue" | "name" | "options"> {}

const DropdownField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
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
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <Dropdown
                {...field}
                {...props}
                items={items}
                value={fieldData?.value as string | null}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));

                  if (props.onChange) {
                    props.onChange(newValue);
                  }
                }}
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
