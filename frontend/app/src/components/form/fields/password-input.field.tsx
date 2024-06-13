import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { PasswordInput } from "@/components/ui/password-input";
import { FormFieldProps } from "@/components/form/type";
import { QuestionMark } from "@/components/display/question-mark";

const PasswordInputField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  ...props
}: FormFieldProps) => {
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
              <PasswordInput value={value ?? ""} {...fieldMethodsWithoutValue} {...props} />
            </FormInput>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default PasswordInputField;
