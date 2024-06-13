import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { InputProps } from "@/components/ui/input";
import { ColorPicker } from "@/components/inputs/color-picker";
import { QuestionMark } from "@/components/display/question-mark";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name"> {}

const ColorField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  ...props
}: InputFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        // Not passing value is needed to prevent error on uncontrolled component
        // eslint-disable-next-line @typescript-eslint/no-unused-vars,no-unused-vars
        const { value, ...fieldMethodsWithoutValue } = field;
        return (
          <div className="flex flex-col">
            <div className="px-1 mb-1 flex justify-between items-center gap-1">
              <FormLabel>
                {label} {rules?.required && "*"}
              </FormLabel>

              {description && <QuestionMark message={description} />}
            </div>

            <FormInput>
              <ColorPicker {...field} className {...props} />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default ColorField;
