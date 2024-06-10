import { FormField, FormInput, FormLabel, FormMessage } from "../@/ui/form";
import { Input } from "../@/ui/input";
import { FormFieldProps } from "./common";

const InputField = ({ defaultValue, label, name, rules, ...props }: FormFieldProps) => {
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
          <div className="flex flex-col items-start">
            <FormLabel className="mb-1">
              {label} {rules?.required && "*"}
            </FormLabel>

            <FormInput>
              <Input {...fieldMethodsWithoutValue} {...props} />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default InputField;
