import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { DatePicker } from "@/components/inputs/date-picker";
import { ComponentProps } from "react";
import { QuestionMark } from "@/components/display/question-mark";

export interface DatetimeFieldProps
  extends FormFieldProps,
    Omit<ComponentProps<typeof DatePicker>, "defaultValue" | "name"> {}

const DatetimeField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
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
            <div className="px-1 mb-1 flex justify-between items-center gap-1">
              <FormLabel>
                {label} {rules?.required && "*"}
              </FormLabel>

              {description && <QuestionMark message={description} />}
            </div>

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
