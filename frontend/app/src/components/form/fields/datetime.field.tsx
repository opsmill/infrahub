import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps, FormAttributeValue } from "@/components/form/type";
import { DatePicker } from "@/components/inputs/date-picker";
import { ComponentProps } from "react";
import { LabelFormField } from "@/components/form/fields/common";
import { formatISO } from "date-fns";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

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
        const fieldData: FormAttributeValue = field.value;

        const handleChange = (newDate: Date) => {
          const newDateValue = formatISO(newDate);
          field.onChange(updateFormFieldValue(newDateValue, defaultValue));
        };

        return (
          <div className="flex flex-col items-start">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />

            <FormInput>
              <DatePicker
                {...field}
                date={field.value?.value}
                value={fieldData?.value ?? ""}
                onChange={handleChange}
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

export default DatetimeField;
