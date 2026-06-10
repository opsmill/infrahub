import { CheckboxCard } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface BooleanFieldProps extends FormFieldProps {}

const BooleanField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  isBulkUpdate,
  description,
  disabled,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
}: BooleanFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={{
        validate: {
          ...rules?.validate,
          required: (fieldData: FormAttributeValue) => {
            if (rules?.required) {
              return (fieldData.value !== undefined && fieldData.value !== null) || "Required";
            }

            return true;
          },
        },
      }}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;
        const value = typeof fieldData.value === "boolean" ? fieldData.value : null;
        const updateValue = (nextValue: boolean) => {
          field.onChange(
            updateFormFieldValue(value === nextValue ? null : nextValue, defaultValue)
          );
        };

        return (
          <div className="space-y-2 py-3">
            <div className="flex items-start justify-between gap-2">
              <LabelFormField
                label={label}
                unique={unique}
                required={!!rules?.required}
                description={description}
                fieldData={fieldData}
              />

              {!disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
                <ResetAction field={field} defaultValue={defaultValue} />
              )}
            </div>

            <FormInput>
              <Row role="group" aria-label={label} className="grid grid-cols-2">
                <CheckboxCard
                  isDisabled={disabled}
                  isSelected={value === true}
                  onChange={() => updateValue(true)}
                >
                  True
                </CheckboxCard>
                <CheckboxCard
                  isDisabled={disabled}
                  isSelected={value === false}
                  onChange={() => updateValue(false)}
                >
                  False
                </CheckboxCard>
              </Row>
            </FormInput>

            <FormMessage className="mt-1" />
          </div>
        );
      }}
    />
  );
};

export default BooleanField;
