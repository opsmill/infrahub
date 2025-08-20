import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { List } from "@/shared/components/list";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

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
                  field.onChange(
                    updateFormFieldValue(newValue.length > 0 ? newValue : null, defaultValue)
                  );
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
