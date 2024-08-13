import { Checkbox } from "@/components/inputs/checkbox";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps, FormAttributeValue } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

export interface CheckboxFieldProps extends FormFieldProps {}

const CheckboxField = ({
  defaultValue = { source: null, value: false },
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: CheckboxFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={{
        validate: {
          ...rules?.validate,
          required: (checked: FormAttributeValue) => {
            if (rules?.required) return checked.value !== undefined && checked.value !== null;

            return true;
          },
        },
      }}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="relative flex flex-col">
            <div className="flex items-center">
              <FormInput>
                <Checkbox
                  {...field}
                  checked={!!fieldData?.value}
                  onChange={(event) => {
                    field.onChange(updateFormFieldValue(event.target.checked, defaultValue));
                  }}
                  {...props}
                />
              </FormInput>

              <LabelFormField
                className="m-0 ml-2"
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                fieldData={fieldData}
              />
            </div>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default CheckboxField;
