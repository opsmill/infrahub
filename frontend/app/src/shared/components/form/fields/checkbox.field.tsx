import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface CheckboxFieldProps extends FormFieldProps {}

const CheckboxField = ({
  defaultValue = { source: null, value: false },
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
      shouldUnregister={shouldUnregister}
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

            <div className="grow">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                deprecation={deprecation}
                description={description}
                fieldData={fieldData}
              />

              <FormMessage className="mt-1" />
            </div>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}
          </div>
        );
      }}
    />
  );
};

export default CheckboxField;
