import { FormFieldProps, FormAttributeValue } from "@/components/form/type";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { JsonEditor } from "@/components/editor/json/json-editor";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

const JsonField = ({
  defaultValue,
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
              <JsonEditor
                {...field}
                value={fieldData?.value as string | undefined}
                onChange={(value) => {
                  if (!value || value === "") {
                    field.onChange({ source: null, value: null });
                  }

                  try {
                    // Store the value as JSON
                    const newValue = JSON.parse(value);
                    field.onChange(updateFormFieldValue(newValue, defaultValue));
                  } catch (e) {
                    field.onChange(updateFormFieldValue(value, defaultValue));
                  }
                }}
                {...props}
                ref={(ref) => {
                  // @ts-expect-error
                  field.ref(ref?._input); // patch lib to be able to focus on form validation fails
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

export default JsonField;
