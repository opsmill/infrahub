import { Checkbox } from "@/components/inputs/checkbox";
import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { QuestionMark } from "@/components/display/question-mark";

export interface CheckboxFieldProps extends FormFieldProps {}

const CheckboxField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  ...props
}: CheckboxFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={{
        validate: {
          ...rules?.validate,
          requireChecked: (checked: boolean) => {
            if (rules?.required) return checked ?? "Required";

            return true;
          },
        },
      }}
      defaultValue={rules?.required ? defaultValue || false : defaultValue}
      render={({ field }) => {
        const { value, ...fieldMethodsWithoutValue } = field;

        return (
          <div className="flex flex-col">
            <div className="flex items-center">
              <FormInput>
                <Checkbox enabled={!!value} {...fieldMethodsWithoutValue} {...props} />
              </FormInput>

              <div className="px-1 mb-1 flex justify-between items-center gap-1">
                <FormLabel>
                  {label} {rules?.required && "*"}
                </FormLabel>

                {description && <QuestionMark message={description} />}
              </div>
            </div>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default CheckboxField;
