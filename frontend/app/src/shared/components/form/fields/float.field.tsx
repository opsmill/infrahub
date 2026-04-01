import { LabelFormField } from "@/shared/components/form/fields/common";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import type { DynamicFloatFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

export interface FloatFieldProps
  extends Omit<DynamicFloatFieldProps, "type" | "onChange">,
    Omit<InputProps, "defaultValue" | "name" | "onChange"> {}

const FloatField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  ...props
}: FloatFieldProps) => {
  const numRef = usePreventScrollOnNumberInput();

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
              <Input
                {...field}
                ref={numRef}
                type="number"
                step="any"
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

export default FloatField;
