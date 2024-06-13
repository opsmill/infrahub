import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { PasswordInput } from "@/components/ui/password-input";
import { FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

const PasswordInputField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
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
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
            />
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
