import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { DatePicker } from "@/components/inputs/date-picker";
import { ComponentProps } from "react";
import { LabelFormField } from "@/components/form/fields/common";

export interface DatetimeFieldProps
  extends FormFieldProps,
    Omit<ComponentProps<typeof DatePicker>, "defaultValue" | "name"> {}

const DatetimeField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: DatetimeFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        return (
          <div className="flex flex-col items-start">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <DatePicker date={field.value} {...field} {...props} />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default DatetimeField;
