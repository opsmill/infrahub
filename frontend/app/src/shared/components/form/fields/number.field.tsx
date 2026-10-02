import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { PoolBackedField } from "@/shared/components/form/pool-backed-field";
import type { DynamicNumberFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

export interface NumberFieldProps
  extends Omit<DynamicNumberFieldProps, "type" | "onChange">,
    Omit<InputProps, "defaultValue" | "name"> {}

const NumberField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  pool,
  shouldUnregister,
  ...props
}: NumberFieldProps) => {
  const numRef = usePreventScrollOnNumberInput();

  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;

        return (
          <PoolBackedField
            name={name}
            label={label}
            description={description}
            unique={unique}
            required={!!rules?.required}
            fieldData={fieldData}
            defaultValue={defaultValue}
            // A number pool has no mask and allocates a plain number, so neither override applies.
            pool={pool}
            valueTabLabel="Value"
            disabled={props.disabled}
            onPoolChange={(value) => field.onChange(updateAttributeFieldValue(value, defaultValue))}
          >
            <FormInput>
              <Input
                {...field}
                ref={numRef}
                type="number"
                value={typeof fieldData?.value === "number" ? fieldData.value : ""}
                onChange={(event) => {
                  const value = event.target.valueAsNumber;
                  field.onChange(updateFormFieldValue(isNaN(value) ? null : value, defaultValue));
                }}
                {...props}
              />
            </FormInput>

            <FormMessage />
          </PoolBackedField>
        );
      }}
    />
  );
};

export default NumberField;
