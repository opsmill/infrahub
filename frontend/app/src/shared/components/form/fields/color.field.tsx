import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { ColorPicker } from "@/shared/components/inputs/color-picker";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import type { InputProps } from "@/shared/components/ui/input";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const ColorField = ({
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
}: InputFieldProps) => {
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
              <ColorPicker
                {...field}
                value={fieldData?.value}
                onChange={(newValue: string) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
                {...props}
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

export default ColorField;
