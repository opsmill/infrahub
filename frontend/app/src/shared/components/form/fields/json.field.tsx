import { JsonEditor } from "@/shared/components/editor/json/json-editor";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

const JsonField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  isBulkUpdate,
  description,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  ...props
}: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
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
                    field.onChange(updateFormFieldValue(null, defaultValue));
                  }

                  try {
                    // Store the value as JSON
                    const newValue = JSON.parse(value);
                    field.onChange(updateFormFieldValue(newValue, defaultValue));
                  } catch (error) {
                    console.error(error);
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

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default JsonField;
