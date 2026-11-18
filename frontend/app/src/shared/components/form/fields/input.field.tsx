import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ResetAction } from "@/shared/components/form/fields/common";
import { PoolBackedField } from "@/shared/components/form/pool-backed-field";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name" | "onChange"> {}

const InputField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  description,
  label,
  name,
  rules,
  unique,
  pool,
  isBulkUpdate,
  shouldUnregister,
  autoFocus,
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
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;

        // Anything the text input cannot show — a from-pool marker, a list — renders empty
        // rather than being asserted into a string.
        const inputValue =
          typeof fieldData?.value === "string" || typeof fieldData?.value === "number"
            ? String(fieldData.value)
            : "";

        return (
          <PoolBackedField
            name={name}
            label={label}
            description={description}
            unique={unique}
            required={!!rules?.required}
            fieldData={fieldData}
            defaultValue={defaultValue}
            // An address/prefix attribute pins the kind to the node being created, so there is
            // nothing to override.
            pool={pool}
            valueTabLabel="Value"
            disabled={props.disabled}
            onPoolChange={(value) => field.onChange(updateAttributeFieldValue(value, defaultValue))}
          >
            <FormInput>
              <Input
                {...field}
                {...props}
                value={inputValue}
                onChange={(event) => {
                  field.onChange(updateFormFieldValue(event.target.value, defaultValue));
                }}
                autoFocus={autoFocus}
              />
            </FormInput>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </PoolBackedField>
        );
      }}
    />
  );
};

export default InputField;
