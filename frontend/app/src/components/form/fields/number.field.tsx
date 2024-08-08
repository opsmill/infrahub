import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { Input, InputProps } from "@/components/ui/input";
import { DynamicNumberFieldProps, FormAttributeValue } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import React from "react";

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

        return (
          <div className="relative mb-2 flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
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
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default NumberField;
