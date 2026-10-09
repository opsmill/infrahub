import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { PoolBackedField } from "@/shared/components/form/pool-backed-field";
import type { DynamicNumberFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import {
  getPoolNumber,
  updateFormFieldValue,
  updateNumberPoolFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";

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
  const trackedPoolId =
    defaultValue?.source?.type === "pool" && defaultValue.source.kind === NUMBER_POOL_KIND
      ? defaultValue.source.id
      : null;
  const trackedNumber = getPoolNumber(defaultValue);

  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;
        const holdsTrackedNumber =
          trackedPoolId !== null &&
          fieldData.source?.type === "pool" &&
          fieldData.source.id === trackedPoolId;

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
            initialTab={trackedPoolId === null ? "value" : "from-pool"}
            disabled={props.disabled}
            onPoolChange={(value) =>
              field.onChange(updateNumberPoolFieldValue(value, fieldData, defaultValue))
            }
          >
            <FormInput>
              <Input
                {...field}
                ref={numRef}
                type="number"
                value={typeof fieldData?.value === "number" ? fieldData.value : ""}
                placeholder={
                  holdsTrackedNumber && trackedNumber !== null ? String(trackedNumber) : undefined
                }
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
