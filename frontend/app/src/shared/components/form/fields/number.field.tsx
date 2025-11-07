import { LabelFormField } from "@/shared/components/form/fields/common";
import { PoolSelector } from "@/shared/components/form/pool-selector";
import { DynamicNumberFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, InputProps } from "@/shared/components/ui/input";

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
            onWheel={(event) => event.currentTarget.blur()}
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
