import { LabelFormField } from "@/components/form/fields/common";
import { PoolSelector } from "@/components/form/pool-selector";
import { DynamicNumberFieldProps, FormAttributeValue } from "@/components/form/type";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Input, InputProps } from "@/components/ui/input";

export interface NumberFieldProps
  extends Omit<DynamicNumberFieldProps, "type">,
    Omit<InputProps, "defaultValue" | "name"> {}

const NumberField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  pools,
  ...props
}: NumberFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        const numberInput = (
          <Input
            {...field}
            type="number"
            value={(fieldData?.value as number) ?? ""}
            onChange={(event) => {
              const value = event.target.valueAsNumber;
              field.onChange(updateFormFieldValue(isNaN(value) ? null : value, defaultValue));
            }}
            {...props}
          />
        );

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
              {pools && pools.length > 0 ? (
                <PoolSelector
                  onChange={(value) =>
                    field.onChange(updateAttributeFieldValue(value, defaultValue))
                  }
                  onReset={() => {
                    if (defaultValue) field.onChange(defaultValue);
                  }}
                  value={fieldData}
                  pools={pools}
                >
                  {numberInput}
                </PoolSelector>
              ) : (
                numberInput
              )}
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default NumberField;
