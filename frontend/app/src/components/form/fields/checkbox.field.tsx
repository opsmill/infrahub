import { LabelFormField } from "@/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/components/form/type";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { Checkbox } from "@/components/inputs/checkbox";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";

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
          <div className="flex gap-2 py-3">
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

            <div className="flex-grow">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                fieldData={fieldData}
              />

              <FormMessage className="mt-1" />
            </div>
          </div>
        );
      }}
    />
  );
};

export default CheckboxField;
