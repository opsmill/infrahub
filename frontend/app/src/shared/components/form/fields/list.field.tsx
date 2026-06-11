import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { List } from "@/shared/components/inputs/list";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

const ListField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  deprecation,
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
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData = field.value;

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              deprecation={deprecation}
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

export default ListField;
