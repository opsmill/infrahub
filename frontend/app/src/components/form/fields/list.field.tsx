import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { LabelFormField } from "@/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/components/form/type";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { List } from "@/components/list";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";

const ListField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={{
        validate: {
          ...rules?.validate,
          required: (fieldData: FormAttributeValue) => {
            if (rules?.required) {
              return (Array.isArray(fieldData.value) && fieldData.value.length > 0) || "Required";
            }

            return true;
          },
        },
      }}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData = field.value;

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
              <List
                {...field}
                {...props}
                value={fieldData?.value ?? ""}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
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

export default ListField;
