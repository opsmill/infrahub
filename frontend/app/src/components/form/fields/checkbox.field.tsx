import { Checkbox } from "@/components/inputs/checkbox";
import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";

const CheckboxField = ({ defaultValue, label, name, rules, ...props }: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => (
        <div className="flex flex-col items-start">
          <div className="flex items-center">
            <FormInput>
              <Checkbox {...field} {...props} />
            </FormInput>

            <FormLabel className="ml-1">
              {label} {rules?.required && "*"}
            </FormLabel>
          </div>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default CheckboxField;
